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
from django.views.decorators.http import require_POST

from ..models import Place, Device, DeviceType, Sensor, SensorType, Unit
from ..services.switchbot_service import SwitchBotService
from ..switchbot_client import list_devices as switchbot_list_devices, get_status as switchbot_get_status
from .switchbot_forms import SwitchBotConfigForm
from ..services.measurement_utils import get_influx_details
from ..influx_client import test_influx_bucket
from .utils import get_switchbot_service_from_place

import json
from icecream import ic
from django.contrib import messages
from ..models import Location
from .switchbot_forms import SwitchBotInfluxStoreForm
from django.core.exceptions import ValidationError


@login_required
def switchbot_management_view(request, place_slug):
    place = get_object_or_404(Place, slug=place_slug)

    # ic("--- Checking SwitchBot Configuration ---")
    # ic(f"Place: {place.name}")
    # ic(f"Enabled: {place.switchbot_enable}")
    # ic(f"Token set: {bool(place.switchbot_token)}")
    # ic(f"Secret set: {bool(place.switchbot_secret)}")
    # ic("------------------------------------")

    # Only redirect if the entire feature is disabled.
    if not place.switchbot_enable:
        messages.warning(request, "SwitchBot integration is not enabled for this place. Please enable it to continue.")
        return redirect(reverse('sensors:place_update', kwargs={'place_slug': place.slug}))

    # If enabled, but credentials are not set, show a warning but still render the page
    if not place.switchbot_token or not place.switchbot_secret:
        messages.warning(request, "SwitchBot API credentials are not fully configured. API features will not work until a Token and Secret are provided.")

    # Test InfluxDB connection if a switchbot-specific store is configured
    influx_test_success = True
    influx_test_message = ""
    if place.switchbot_influx_store:
        influx_store = place.switchbot_influx_store
        success, message, _ = test_influx_bucket(
            url=influx_store.url,
            token=influx_store.token,
            org=influx_store.org,
            bucket_name=influx_store.bucket_name
        )
        influx_test_success = success
        influx_test_message = message
    else:
        # If no specific store, check the default
        if place.default_influx_store:
            influx_store = place.default_influx_store
            success, message, _ = test_influx_bucket(
                url=influx_store.url,
                token=influx_store.token,
                org=influx_store.org,
                bucket_name=influx_store.bucket_name
            )
            influx_test_success = success
            influx_test_message = message

    # Fetch local devices and sensors for this place
    local_devices = Device.objects.filter(
        location__place=place,
        is_switchbot=True
    ).select_related('location').order_by('name')

    local_sensors = Sensor.objects.filter(
        device__location__place=place,
        device__is_switchbot=True
    ).select_related('device', 'device__location', 'sensor_type').order_by('device__name', 'name')

    context = {
        'place': place,
        'local_devices': local_devices,
        'local_sensors': local_sensors,
        'switchbot_devices_count': local_devices.count(),
        'switchbot_sensors_count': local_sensors.count(),
    }
    return render(request, 'sensors/switchbot_management.html', context)


@login_required
def switchbot_influx_store_edit_view(request, place_slug):
    place = get_object_or_404(Place, slug=place_slug)
    form = SwitchBotInfluxStoreForm(instance=place, place=place)
    return render(request, 'sensors/partials/_switchbot_influx_store_form.html', {
        'place': place,
        'form': form
    })


@login_required
@require_POST
def switchbot_influxstore_update(request, place_slug):
    place = get_object_or_404(Place, slug=place_slug)
    form = SwitchBotInfluxStoreForm(request.POST, instance=place, place=place)
    if form.is_valid():
        form.save()
        message = "SwitchBot InfluxDB store updated successfully."
        messages.success(request, message)
    else:
        message = "There was an error updating the InfluxDB store."
        messages.error(request, message)

    # Re-render the card to be returned to HTMX
    response = render(request, 'sensors/includes/switchbot_influxstore_card.html', {'place': place})

    # Add trigger to close modal and show toast
    response['HX-Trigger'] = json.dumps({
        "closeModal": "#htmx-modal",
        "showToast": {"message": message}
    })
    return response


@login_required
def switchbot_existing_devices_view(request, place_slug):
    place = get_object_or_404(Place, slug=place_slug)
    local_devices = Device.objects.filter(
        location__place=place,
        is_switchbot=True
    ).select_related('location').order_by('name')

    context = {
        'place': place,
        'local_devices': local_devices,
    }
    return render(request, 'sensors/includes/switchbot_existing_devices_card.html', context)


@login_required
def switchbot_api_sync_view(request, place_slug):
    place = get_object_or_404(Place, slug=place_slug)
    api_status = {}
    devices_to_display = []
    influx_store = None
    influx_test_success = None
    influx_test_message = None

    try:
        # Determine which InfluxDB store to use (SwitchBot specific or default)
        influx_store = place.switchbot_influx_store or place.default_influx_store

        # Test InfluxDB connection only if a store is explicitly configured
        if influx_store:
            success, message, _ = test_influx_bucket(
                url=influx_store.url,
                token=influx_store.token,
                org=influx_store.org,
                bucket_name=influx_store.bucket_name
            )
            influx_test_success = success
            influx_test_message = message

        # Fetch devices from SwitchBot API
        api_response = switchbot_list_devices(token=place.switchbot_token, secret=place.switchbot_secret)
        if api_response.get('statusCode') != 100:
            raise Exception(api_response.get('message', 'Unknown API error'))

        api_devices_body = api_response.get('body', {})
        all_api_devices = api_devices_body.get('deviceList', []) + api_devices_body.get('infraredRemoteList', [])
        api_status = {'success': True}

        # Process devices
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
        ic(f"SwitchBot API sync failed: {e}")
        api_status = {'success': False, 'error_message': str(e)}

    context = {
        'place': place,
        'devices': devices_to_display,
        'api_status': api_status,
        'influx_test_success': influx_test_success,
        'influx_store': influx_store,
        'influx_test_message': influx_test_message,
    }

    return render(request, 'sensors/partials/_switchbot_sync_results.html', context)


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
                if key.lower() in ['version', 'deviceid', 'devicetype', 'hubdeviceid']:
                    continue

                standardized_name = KEY_MAP.get(key)
                if standardized_name:
                    # Special handling for battery
                    if key == 'battery':
                        if 'battery level' not in existing_sensor_types and 'battery voltage' not in existing_sensor_types:
                            try:
                                val_float = float(value)
                                if val_float > 50:
                                    display_name = 'Battery Level'
                                else:
                                    display_name = 'Battery Voltage'
                            except (ValueError, TypeError):
                                display_name = 'Battery Level'  # Default
                            missing_sensors.append({'name': key, 'display_name': display_name, 'value': value})
                    elif standardized_name.lower() not in existing_sensor_types:
                        missing_sensors.append({'name': key, 'display_name': standardized_name, 'value': value})
            context['missing_switchbot_sensors'] = missing_sensors

        # If the device is not imported, show what would be created
        else:
            inspection_results = []
            for key, value in body.items():
                if key in ['version', 'deviceId', 'deviceType', 'hubDeviceId']:
                    continue

                sensor_name = KEY_MAP.get(key, key.capitalize())

                # Custom logic to determine battery sensor type by value
                if key == 'battery':
                    if float(value) > 50:
                        sensor_name = 'Battery Level'
                    else:
                        sensor_name = 'Battery Voltage'

                influx_details = get_influx_details(sensor_name)
                influx_group = influx_details[0] if influx_details else 'reading'
                influx_field = influx_details[1] if influx_details else 'value'

                full_measurement_name = f"switchbot_{slugify(device_name)}_{influx_group}"

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
            data_store='DIRECT',
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
            ic("--- switchbot_config_update_view form_valid ---")
            ic(form.cleaned_data)
            form.save()
            response = render(request, 'sensors/includes/switchbot_settings_card.html', {'place': place})
            response['HX-Trigger'] = '{"closeModal": "#htmx-modal"}'
            return response
    else:
        form = SwitchBotConfigForm(instance=place, place=place)

    return render(request, 'sensors/partials/_switchbot_config_form.html', {
        'form': form,
        'place': place
    })


@login_required
@require_POST
def import_switchbot_device_view(request, place_slug):
    """
    Imports a SwitchBot device and its sensors into the local database by calling the service.
    """
    place = get_object_or_404(Place, slug=place_slug)
    device_id = request.GET.get('device_id')
    location_id = request.POST.get('location_id')
    is_active_from_form = request.POST.get('is_active') == 'on'
    device_name = request.POST.get('device_name', device_id) # Get name from hidden form input

    if location_id:
        location = get_object_or_404(Location, pk=location_id, place=place)
    else:
        location = place.get_unassigned_location()

    try:
        if not location.is_active:
            is_active = False
        else:
            is_active = is_active_from_form

        # Call the service to handle the import logic
        service = SwitchBotService(place)
        device, imported_sensors, body = service.import_device(device_id, device_name, location, is_active)

    except ValidationError as e:
        error_message = "; ".join([f"{key.replace('_', ' ').title()}: {val[0]}" for key, val in e.message_dict.items()])
        ic(f"Validation error importing SwitchBot device {device_id}: {error_message}")
        response = HttpResponse(status=204)
        response['HX-Trigger'] = json.dumps({
            "showToast": {
                "message": f"Import Failed: {error_message}",
                "type": "warning"
            },
            "closeModal": "#htmx-modal"
        })
        return response
    except Exception as e:
        ic(f"Failed to import SwitchBot device {device_id}: {e}")
        response = HttpResponse(status=204)
        response['HX-Trigger'] = json.dumps({
            "showToast": {
                "message": f"Error importing device: {e}",
                "type": "error"
            },
            "closeModal": "#htmx-modal"
        })
        return response

    # On success, return a 204 No Content response with triggers
    # to close the modal, show a toast, and refresh both tables.
    response = HttpResponse(status=204)

    triggers = {
        "closeModal": "#htmx-modal",
        "refreshSyncList": True,
        "refreshDeviceList": True,
    }

    if imported_sensors:
        success_toast_html = render_to_string(
            'sensors/partials/_import_success_toast.html',
            {'device': device, 'sensors': imported_sensors}
        )
        triggers["showToast"] = {
            "message": success_toast_html,
            "type": "success"
        }

    response['HX-Trigger'] = json.dumps(triggers)
    return response


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
            context['raw_api_response'] = json.dumps(status_data, indent=2)
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

@login_required
def switchbot_import_options_view(request, place_slug, device_id):
    """
    Displays a modal with options for importing a new SwitchBot device.
    """
    place = get_object_or_404(Place, slug=place_slug)
    device_name = request.GET.get('name', device_id)
    potential_sensors = []
    try:
        status_data = switchbot_get_status(device_id, place.switchbot_token, place.switchbot_secret)
        if status_data.get('statusCode') == 100:
            body = status_data.get('body', {})
            from ..services.switchbot_service import KEY_MAP
            for key, value in body.items():
                if key in ['version', 'deviceId', 'deviceType', 'hubDeviceId']:
                    continue
                sensor_name = KEY_MAP.get(key, key.capitalize())
                potential_sensors.append({'sensor_name': sensor_name})
    except Exception as e:
        ic(f"Could not pre-fetch sensor list for import options: {e}")

    # Default to the 'Unassigned' location
    default_location = place.get_unassigned_location()

    context = {
        'place': place,
        'device_id': device_id,
        'device_name': device_name,
        'locations': place.locations.all(),
        'location': default_location, # Provide default location for initial form state
        'potential_sensors': potential_sensors,
        'form_url': reverse('sensors:import_switchbot_device', args=[place.slug]) + f'?device_id={device_id}'
    }
    return render(request, 'sensors/partials/_switchbot_import_form.html', context)
