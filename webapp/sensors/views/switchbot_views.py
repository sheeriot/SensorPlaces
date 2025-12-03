from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.text import slugify
from django.template.loader import render_to_string
from django.db.models import Count, Q
from django.db.models.functions import Lower

from ..models import Place, Device, DeviceType, Sensor, SensorType, Unit
from ..services.switchbot_service import SwitchBotService
from ..switchbot_client import list_devices as switchbot_list_devices, get_status as switchbot_get_status
from .switchbot_forms import SwitchBotConfigForm
from ..services.measurement_utils import get_influx_details

import json
from icecream import ic
from django.contrib import messages
from ..models import Location

@login_required
def switchbot_management_view(request, place_slug):
    place = get_object_or_404(Place, slug=place_slug)
    api_status = {}
    devices_to_display = []

    if not place.switchbot_enable or not place.switchbot_token or not place.switchbot_secret:
        return redirect(reverse('sensors:place_update', kwargs={'place_slug': place.slug}))

    try:
        api_response = switchbot_list_devices(token=place.switchbot_token, secret=place.switchbot_secret)
        api_devices_body = api_response['body']
        all_api_devices = api_devices_body.get('deviceList', []) + api_devices_body.get('infraredRemoteList', [])
        api_status = {'success': True}

        existing_devices = Device.objects.filter(is_switchbot=True, device_id__isnull=False).select_related('location__place')
        existing_device_map = {d.device_id: d for d in existing_devices}

        for device in all_api_devices:
            device_id = device['deviceId']
            device_info = {
                'name': device['deviceName'],
                'type': device.get('deviceType', 'Infrared Remote'),
                'id': device_id,
                'hub_id': device.get('hubDeviceId'),
                'local_device': None,
            }

            if device_id in existing_device_map:
                local_device = existing_device_map[device_id]
                device_info['local_device'] = local_device
                if local_device.location.place.pk == place.pk:
                    device_info['status'] = 'imported_here'
                else:
                    device_info['status'] = 'in_other_place'
                    device_info['other_place_name'] = local_device.location.place.name
            else:
                device_info['status'] = 'new'

            devices_to_display.append(device_info)

        devices_to_display.sort(key=lambda x: (x['status'] != 'new', x['status']))

    except Exception as e:
        api_status = {'success': False, 'error_message': str(e)}

    context = {
        'place': place,
        'devices': devices_to_display,
        'api_status': api_status,
    }
    return render(request, 'sensors/switchbot_management.html', context)


@login_required
def switchbot_inspect_api_device_view(request, place_slug, device_id):
    place = get_object_or_404(Place, slug=place_slug)
    device_name = request.GET.get('name', device_id)

    # Try to find the local device
    local_device = Device.objects.filter(device_id=device_id).first()

    context = {
        'place': place,
        'device_id': device_id,
        'device_name': device_name,
        'device': local_device
    }

    try:
        status_data = switchbot_get_status(device_id, place.switchbot_token, place.switchbot_secret)
        if status_data.get('statusCode') != 100:
            raise Exception(status_data.get('message', 'Unknown API error'))

        body = status_data.get('body', {})

        from ..services.switchbot_service import KEY_MAP

        # If the device is imported, find missing sensors
        if local_device:
            existing_sensor_types = set(s.lower() for s in local_device.sensors.values_list('sensor_type__name', flat=True))
            missing_sensors = []
            for key, value in body.items():
                standardized_name = KEY_MAP.get(key)
                if standardized_name and standardized_name.lower() not in existing_sensor_types:
                     # Check for keys that we don't want to treat as sensors
                    if key.lower() in ['version', 'deviceid', 'devicetype', 'hubdeviceid']:
                        continue
                    missing_sensors.append({'name': key, 'display_name': standardized_name, 'value': value})
            context['missing_switchbot_sensors'] = missing_sensors

        # If the device is not imported, show what would be created
        else:
            inspection_results = []
            for key, value in body.items():
                if key in ['version', 'deviceId', 'deviceType', 'hubDeviceId']:
                    continue

                sensor_name = KEY_MAP.get(key, key.capitalize())

                # Custom logic for battery
                if sensor_name == 'Battery':
                    influx_group = 'battery'
                    influx_field = 'battery'
                else:
                    influx_details = get_influx_details(sensor_name)
                    influx_group = influx_details[0] if influx_details else 'reading'
                    influx_field = influx_details[1] if influx_details else 'value'

                full_measurement_name = f"{slugify(device_name)}_{influx_group}"

                inspection_results.append({
                    'sensor_name': sensor_name,
                    'current_reading': value,
                    'influx_measurement': full_measurement_name,
                    'influx_field': influx_field,
                })
            context['results'] = inspection_results

        context['raw_data'] = json.dumps(body, indent=2)
        context['success'] = True

    except Exception as e:
        context['success'] = False
        context['error_message'] = str(e)

    return render(request, 'sensors/partials/_switchbot_inspection_content.html', context)


@login_required
def add_switchbot_sensor(request, place_slug, device_pk):
    """
    Handles the HTMX request to add a new SwitchBot sensor to a device.
    """
    ic("AddSwitchBotSensor: Received request.")
    device = get_object_or_404(Device, pk=device_pk, location__place__slug=place_slug)
    place = device.location.place

    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return HttpResponse("Invalid request method.", status=405)

    sensor_type_name = request.POST.get('sensor_type_name')
    ic(f"AddSwitchBotSensor: Attempting to add sensor of type '{sensor_type_name}' to device '{device.name}'.")

    if not sensor_type_name:
        messages.error(request, "Sensor type not provided.")
        return HttpResponse("Sensor type not provided.", status=400)

    # --- Create Sensor, SensorType, and Unit ---
    unit_map = {
        'Temperature': ('Celsius', '°C'),
        'Humidity': ('Relative Humidity', '%RH'),
        'Battery': ('Percent', '%'),
        'Light Level': ('Level', 'level')
    }
    defaults = {}
    if sensor_type_name == 'Battery':
        defaults['default_graph_type'] = 'LINE'

    if sensor_type_name in unit_map:
        unit_name, unit_symbol = unit_map[sensor_type_name]
        unit, _ = Unit.objects.get_or_create(name=unit_name, defaults={'symbol': unit_symbol})
        defaults['unit'] = unit

    sensor_type, created = SensorType.objects.get_or_create(name=sensor_type_name, defaults=defaults)
    if created:
        ic(f"AddSwitchBotSensor: Created new SensorType: '{sensor_type.name}'")

    if not Sensor.objects.filter(device=device, sensor_type=sensor_type).exists():
        new_sensor = Sensor.objects.create(
            device=device,
            name=sensor_type_name,
            sensor_type=sensor_type,
            is_active=False,
            data_type='DIRECT',
        )
        ic(f"AddSwitchBotSensor: Successfully created new Sensor '{new_sensor.name}'.")
        messages.success(request, f"Successfully added sensor '{new_sensor.name}'. It is inactive by default.")
    else:
        ic(f"AddSwitchBotSensor: Sensor of type '{sensor_type_name}' already exists for this device.")
        messages.warning(request, f"Sensor '{sensor_type_name}' already exists for this device.")

    # --- Prepare HTMX OOB (Out-of-Band) Swaps ---
    # 1. Re-render the device detail card (for sensor counts)
    device = Device.objects.annotate(
        active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)),
        inactive_sensors_count=Count('sensors', filter=Q(sensors__is_active=False))
    ).get(pk=device.pk)
    hub_device = None
    if device.is_switchbot and device.hub_id:
        try:
            hub_device = Device.objects.get(device_id=device.hub_id, location__place=place)
        except Device.DoesNotExist:
            pass

    device_detail_html = render_to_string(
        'sensors/includes/device_detail_card.html',
        {'device': device, 'place': place, 'hub_device': hub_device}
    )

    # 2. Re-render the sensor list
    device.sensors_sorted = device.sensors.select_related('sensor_type', 'sensor_type__unit').order_by('-is_active', Lower('name'))
    sensor_list_html = render_to_string(
        'sensors/includes/sensor_list_card.html',
        {'device': device, 'place': place, 'request': request, 'sensors': device.sensors_sorted}
    )

    # 3. Re-run inspection to get the main content for the response
    context = {
        'device': device,
        'place': place,
        'oob_device_detail': device_detail_html,
        'oob_sensor_list': sensor_list_html,
        'success': True,
        'missing_switchbot_sensors': [],
        'switchbot_inspect_data': None,
    }

    # After adding a sensor, re-run the inspection logic to find remaining sensors
    try:
        status_data = switchbot_get_status(device.device_id, place.switchbot_token, place.switchbot_secret)
        if status_data.get('statusCode') == 100:
            body = status_data.get('body', {})
            # Get a fresh list of sensor types for the device
            existing_sensor_types = set(s.lower() for s in device.sensors.values_list('sensor_type__name', flat=True))

            from ..services.switchbot_service import KEY_MAP
            missing_sensors = []
            for key, value in body.items():
                if key.lower() in ['version', 'deviceid', 'devicetype', 'hubdeviceid']:
                    continue

                standardized_name = KEY_MAP.get(key)
                if standardized_name and standardized_name.lower() not in existing_sensor_types:
                    missing_sensors.append({'name': key, 'display_name': standardized_name, 'value': value})

            context['missing_switchbot_sensors'] = missing_sensors
            context['switchbot_inspect_data'] = json.dumps(body, indent=2)
    except Exception as e:
        ic(f"Error during re-inspection after add: {e}")
        context['success'] = False
        context['error_message'] = "Could not re-run device inspection after adding sensor."


    return render(request, 'sensors/partials/_switchbot_inspection_content.html', context)

@login_required
def switchbot_config_update_view(request, place_slug):
    place = get_object_or_404(Place, slug=place_slug)

    if request.method == 'POST':
        form = SwitchBotConfigForm(request.POST, instance=place)
        if form.is_valid():
            form.save()
            response = render(request, 'sensors/partials/switchbot_settings_card.html', {'place': place})
            response['HX-Trigger'] = 'closeModal'
            return response
    else:
        form = SwitchBotConfigForm(instance=place)

    return render(request, 'sensors/switchbot_config_form.html', {
        'form': form,
        'place': place,
        'form_url': reverse('sensors:switchbot_config_update', args=[place.slug])
    })


@login_required
def import_switchbot_device_view(request, place_slug):
    place = get_object_or_404(Place, slug=place_slug)

    if request.method != 'POST':
        return HttpResponse("Invalid request method.", status=405)

    device_id_to_import = request.POST.get('device_id')
    location_id = request.POST.get('location_id')

    target_location = None
    is_active = False
    if location_id:
        try:
            target_location = place.locations.get(id=location_id)
            is_active = target_location.is_active
        except Location.DoesNotExist:
            return HttpResponse("Invalid location specified.", status=400)
    else:
        target_location = place.get_unassigned_location()

    try:
        api_devices_body = switchbot_list_devices(token=place.switchbot_token, secret=place.switchbot_secret)['body']
        all_api_devices = api_devices_body.get('deviceList', []) + api_devices_body.get('infraredRemoteList', [])
        device_to_import = next((d for d in all_api_devices if d['deviceId'] == device_id_to_import), None)

        if not device_to_import:
            return HttpResponse("Device not found in SwitchBot account.", status=404)

        device_type, _ = DeviceType.objects.get_or_create(name='Data Logger')

        local_device, created = Device.objects.get_or_create(
            device_id=device_id_to_import,
            defaults={
                'name': device_to_import.get('deviceName', 'New SwitchBot Device'),
                'is_switchbot': True,
                'location': target_location,
                'model': device_to_import.get('deviceType', 'Infrared Remote'),
                'hub_id': device_to_import.get('hubDeviceId'),
                'is_active': is_active,
                'manufacturer': 'SwitchBot',
                'device_type': device_type,
            }
        )

        service = SwitchBotService(place)
        status_data = switchbot_get_status(device_id_to_import, place.switchbot_token, place.switchbot_secret)
        if status_data.get('statusCode') == 100:
            body = status_data.get('body', {})
            service._process_readings(local_device, body, activate_sensors=is_active)

    except Exception as e:
        response = HttpResponse(f"Failed to import device: {e}", status=500)
        response['HX-Retarget'] = '#error-container'
        response['HX-Reswap'] = 'innerHTML'
        return response

    device_info = {
        'name': local_device.name,
        'type': local_device.model,
        'id': local_device.device_id,
        'hub_id': local_device.hub_id,
        'status': 'imported_here',
        'local_device': local_device,
    }

    return render(request, 'sensors/partials/switchbot_device_row.html', {'device': device_info, 'place': place})


class SwitchbotInspectView(LoginRequiredMixin, View):
    def get(self, request, place_slug, pk):
        device = get_object_or_404(Device, pk=pk, location__place__slug=place_slug)
        place = device.location.place
        context = {'device': device, 'place': place}

        try:
            status_data = switchbot_get_status(device.device_id, place.switchbot_token, place.switchbot_secret)
            if status_data.get('statusCode') != 100:
                raise Exception(status_data.get('message', "Unknown API Error"))

            body = status_data.get('body', {})
            existing_sensor_types = set(
                s.lower() for s in device.sensors.select_related('sensor_type')
                                .filter(sensor_type__name__isnull=False)
                                .values_list('sensor_type__name', flat=True)
            )

            from ..services.switchbot_service import KEY_MAP
            missing_sensors = []
            for key, value in body.items():
                if key.lower() in ['version', 'deviceid', 'devicetype', 'hubdeviceid']:
                    continue

                standardized_name = KEY_MAP.get(key)
                if standardized_name and standardized_name.lower() not in existing_sensor_types:
                    missing_sensors.append({
                        'name': key,
                        'display_name': standardized_name,
                        'value': value,
                    })

            context['missing_switchbot_sensors'] = missing_sensors
            context['switchbot_inspect_data'] = json.dumps(body, indent=2)
            context['success'] = True
            context['device'] = device

        except Exception as e:
            ic(f"Failed to get SwitchBot status for inspection: {e}")
            context['success'] = False
            context['error_message'] = str(e)

        return render(request, 'sensors/partials/_switchbot_inspection_content.html', context)


@login_required
def fetch_switchbot_reading(request, place_slug, pk):
    device = get_object_or_404(Device, pk=pk, location__place__slug=place_slug)
    place = device.location.place

    if not device.is_switchbot or not device.device_id:
        messages.error(request, f"Device '{device.name}' is not a configured SwitchBot device.")
        return redirect(device.get_absolute_url())

    try:
        service = SwitchBotService(place)
        readings_found = service.fetch_and_process_single_device_reading(device)

        if readings_found > 0:
            messages.success(request, f"Successfully processed {readings_found} reading(s) for {device.name}.")
        else:
            messages.info(request, f"No new readings were available from the API for {device.name}.")

    except Exception as e:
        ic(f"Failed to fetch readings for {device.name}: {e}")
        messages.error(request, f"Failed to fetch readings for {device.name}: {e}")

    return redirect(device.get_absolute_url())
