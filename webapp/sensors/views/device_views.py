from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse, Http404
import json
from icecream import ic
# import logging # No longer needed

from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet, Prefetch
from django.utils.safestring import mark_safe
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta

from ..models import Place, Location, Device, Sensor, SensorReading, SensorType, Unit
from .device_forms import DeviceForm
from .mixins import PlaceAnnotationMixin, ReferrerMixin
from .views_fun import get_place_counts, get_annotated_locations, get_live_counts_context
from .sensor_forms import SensorForm, LoRaWANSensorForm
from ..utils import get_sensor_readings, generate_sparkline, get_latest_influx_reading, update_sensor_live_value
from ..decorators import log_execution_time
from ..switchbot_client import get_status

from django.contrib.auth.decorators import login_required
from django.contrib import messages

# Maps SwitchBot API keys to a user-friendly name and a default Unit.
# Format: 'api_key': ('Friendly Name', 'Unit Name', 'Unit Symbol')
# This allows us to handle various sensor types from the API.
SWITCHBOT_KEY_MAP = {
    'temperature': ('Temperature', 'Celsius', '°C'),
    'humidity': ('Humidity', 'Relative Humidity', '%RH'),
    'battery': ('Battery', 'Percent', '%'),
    'leakState': ('Water Leak', 'Binary', ''),
    'status': ('Status', 'Binary', ''),
    'moveDetected': ('Motion', 'Binary', ''),
    'brightness': ('Light', 'Level', ''),
}

# logger = logging.getLogger(__name__) # No longer needed

@login_required
def device_inspect_view(request, place_slug, pk):
    device = get_object_or_404(
        Device.objects.select_related('location', 'location__place'),
        pk=pk,
        location__place__slug=place_slug
    )
    context = {'device': device, 'place': device.location.place, 'place_slug': place_slug}

    if not device.is_switchbot or not device.device_id:
        context['error'] = "This is not a SwitchBot device with a valid device ID."
    else:
        try:
            status_data = get_status(device.device_id)
            context['inspect_data'] = json.dumps(status_data, indent=2)

            if status_data.get('statusCode') == 100:
                body = status_data.get('body', {})

                # Get existing sensor type names for this device, case-insensitive
                existing_sensor_types = set(
                    s.lower() for s in device.sensors.select_related('sensor_type')
                                  .filter(sensor_type__name__isnull=False)
                                  .values_list('sensor_type__name', flat=True)
                )

                # Exclude non-sensor keys from the API response
                excluded_keys = {'version', 'deviceid', 'devicetype', 'hubdeviceid'}

                # Find keys in the API body that are not yet sensors on this device
                missing_sensors = []
                for key, value in body.items():
                    if key.lower() not in existing_sensor_types and key.lower() not in excluded_keys:
                        missing_sensors.append({
                            'name': key,
                            'value': value,
                        })

                context['missing_sensors'] = missing_sensors

        except Exception as e:
            context['error'] = f"Failed to get SwitchBot status: {e}"

    return render(request, 'sensors/partials/device_inspect_modal_content.html', context)


@require_POST
@login_required
def add_switchbot_sensor(request, place_slug, pk):
    device = get_object_or_404(Device, pk=pk, location__place__slug=place_slug)
    sensor_to_add_raw = request.POST.get('sensor_type')
    value_to_add = request.POST.get('value')

    if not sensor_to_add_raw:
        return HttpResponse("Sensor type not provided.", status=400)

    try:
        sensor_type_name = sensor_to_add_raw.capitalize()
        unit = None
        if sensor_type_name == 'Temperature':
            unit, _ = Unit.objects.get_or_create(name="Celsius", defaults={'symbol': '°C'})
        elif sensor_type_name == 'Humidity':
            unit, _ = Unit.objects.get_or_create(name="Relative Humidity", defaults={'symbol': '%RH'})
        elif sensor_type_name == 'Battery':
            unit, _ = Unit.objects.get_or_create(name="Percent", defaults={'symbol': '%'})

        sensor_type, _ = SensorType.objects.get_or_create(
            name__iexact=sensor_type_name,
            defaults={'name': sensor_type_name, 'default_unit': unit}
        )

        sensor, created = Sensor.objects.get_or_create(
            device=device,
            sensor_type=sensor_type,
            defaults={'name': f'{device.name} {sensor_type.name}'}
        )

        if created and value_to_add is not None:
            try:
                sensor.cached_reading_value = float(value_to_add)
                sensor.cached_reading_timestamp = timezone.now()
                sensor.save(update_fields=['cached_reading_value', 'cached_reading_timestamp'])
            except (ValueError, TypeError):
                ic(f"Could not parse value '{value_to_add}' for new sensor {sensor.name}")

        if created:
            sensor.live_value = sensor.cached_reading_value
            sensor_row_html = render_to_string(
                'sensors/partials/sensor_row.html',
                {
                    'sensor': sensor,
                    'place': device.location.place,
                    'device': device,
                    'device_is_active': device.is_active,
                    'parent_is_active': device.location.is_active,
                    'narrow_view': False,
                    'object_name': sensor.name
                }
            )

            ic("Generated sensor row HTML for trigger:", sensor_row_html)

            response = HttpResponse(status=204)
            response['HX-Trigger'] = json.dumps({
                'sensorAdded': {
                    'sensorType': sensor_to_add_raw, # Use the raw name for the JS selector
                    'sensorHTML': sensor_row_html,
                    'deviceId': device.pk
                }
            })
            return response
        else:
            response = HttpResponse(status=204)
            response['HX-Trigger'] = json.dumps({'sensorAlreadyExists': {'sensorType': sensor_to_add_raw}})
            return response

    except Exception as e:
        ic(f"Error adding SwitchBot sensor: {e}", exc_info=True)
        return HttpResponse(f'<div class="badge bg-danger">Error</div>', status=500)


# Device Views
class DeviceListView(LoginRequiredMixin, PlaceAnnotationMixin, ListView):
    model = Location
    context_object_name = 'locations'
    template_name = 'sensors/device_list.html'

    def get_queryset(self) -> QuerySet[Location]:
        # Prefetch devices for each location
        devices_prefetch = Prefetch(
            'devices',
            queryset=Device.objects.annotate(
                sensors_active_count=Count('sensors', filter=Q(sensors__is_active=True)),
                sensors_inactive_count=Count('sensors', filter=Q(sensors__is_active=False))
            ).order_by('-is_active', 'name'),
            to_attr='devices_sorted'
        )

        qs = get_annotated_locations(self._place).prefetch_related(devices_prefetch)
        # We no longer exclude 'unassigned-devices' so that it can be rendered in the unassigned_devices_card
        # qs = qs.exclude(slug='unassigned-devices')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'

        # Add hide_inactive state from GET param or cookie
        hide_inactive_param = self.request.GET.get('hide_inactive')
        if hide_inactive_param is not None:
            context['hide_inactive'] = hide_inactive_param.lower() == 'true'
        else:
            hide_inactive_cookie = self.request.COOKIES.get('hideInactive_device', 'false')
            context['hide_inactive'] = hide_inactive_cookie.lower() == 'true'

        # Add place to context
        place = self.get_place()
        context['place'] = place
        unassigned_devices = Device.objects.filter(location__place=place, location__slug='unassigned-devices').order_by('-is_active', 'name')
        context['unassigned_devices'] = unassigned_devices

        # Add live counts to context
        context.update(get_live_counts_context(place))

        # Get location if specified
        location_pk = self.request.GET.get('location', None)
        if location_pk:
            context['location'] = get_object_or_404(Location, pk=location_pk, place=place)

        # If this is the unassigned-devices location view, force hide_inactive to be off.
        context['lock_hide_inactive'] = False
        if context.get('location') and context['location'].slug == 'unassigned-devices':
            context['hide_inactive'] = False
            context['lock_hide_inactive'] = True

        return context

class UnassignedDeviceListView(LoginRequiredMixin, PlaceAnnotationMixin, ListView):
    model = Device
    context_object_name = 'unassigned_devices'
    template_name = 'sensors/unassigned_devices_list.html'

    def get_queryset(self):
        place = self.get_place()
        return Device.objects.filter(location__place=place, location__slug='unassigned-devices').order_by('-is_active', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        place = self.get_place()
        context['place'] = place
        context['model_name'] = 'device'
        context.update(get_live_counts_context(place))

        # Lock the hide_inactive switch to off for this view
        context['hide_inactive'] = False
        context['lock_hide_inactive'] = True

        return context

@method_decorator(log_execution_time, name='dispatch')
class DeviceDetailView(LoginRequiredMixin, PlaceAnnotationMixin, DetailView):
    model = Device
    context_object_name = 'device'
    template_name = 'sensors/device_detail.html'
    object: Device

    def get_queryset(self) -> QuerySet[Device]:
        if not hasattr(self, '_queryset'):
            self._place_slug = self.kwargs.get('place_slug')
            place = get_object_or_404(Place, slug=self._place_slug)
            self._place = place
            base_queryset = super().get_queryset()
            self._queryset = base_queryset.filter(location__place=place)\
                .annotate(
                    active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)),
                    inactive_sensors_count=Count('sensors', filter=Q(sensors__is_active=False))
                ).prefetch_related(
                    Prefetch(
                        'sensors',
                        queryset=Sensor.objects.select_related('sensor_type', 'sensor_type__default_unit')
                                              .order_by('-is_active', Lower('name')),
                        to_attr='sensors_sorted'
                    ))
        return self._queryset

    def get(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
        except Http404:
            # Device not found - redirect to place detail with toast
            place_slug = self.kwargs.get('place_slug')
            messages.error(request, "Device Not Found") # Fallback message

            return HttpResponseRedirect(reverse('sensors:place_detail', kwargs={'place_slug': place_slug}))

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        device = self.object
        location = device.location

        context['model_name'] = 'device'
        context['place'] = self._place
        context['location'] = location
        context['sensors'] = device.sensors_sorted
        context['locations'] = get_annotated_locations(self._place)
        context['absolute_url'] = self.request.build_absolute_uri()

        # --- Smart Data Fetching for Sensors ---
        self.fetch_live_data_for_sensors(context['sensors'])

        # Add hide_inactive state from GET param or cookie
        hide_inactive_param = self.request.GET.get('hide_inactive')
        if hide_inactive_param is not None:
            context['hide_inactive'] = hide_inactive_param.lower() == 'true'
        else:
            hide_inactive_cookie = self.request.COOKIES.get('hideInactive_sensor', 'false')
            context['hide_inactive'] = hide_inactive_cookie.lower() == 'true'

        # Add live counts to context
        context.update(get_live_counts_context(self._place))

        # ic(context['device'].__dict__)
        # ic(context['sensors'])
        # ic(context['locations'])
        return context

    def fetch_live_data_for_sensors(self, sensors):
        """
        Iterate through sensors and fetch live data if it's stale.
        This is now a simple wrapper around the utility function.
        """
        # The logic to group SwitchBot calls is now handled inside the util,
        # or accepted as a trade-off for simplicity in the live-value-per-sensor context.
        # For a full device page refresh, this is still efficient enough.
        for sensor in sensors:
            update_sensor_live_value(sensor)

        # Attach the (potentially updated) cached value to live_value for the template
        for sensor in sensors:
            sensor.live_value = sensor.cached_reading_value

class DeviceCreateView(LoginRequiredMixin, PlaceAnnotationMixin, ReferrerMixin, CreateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'
    object: Device

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place and locations
        self._place = self.get_place()
        self._locations = get_annotated_locations(self._place)

        # Initialize location and inactive_help_text
        self._location = None

        # Get location if specified in URL
        location_slug = self.kwargs.get('location_slug', None)
        if location_slug:
            self._location = get_object_or_404(Location, slug=location_slug, place=self._place)

    def get_initial(self):
        initial = super().get_initial()

        # Set location from URL if available
        if self._location:
            initial['location'] = self._location

        duplicate_pk = self.request.GET.get('duplicate')

        if duplicate_pk:
            try:
                device_to_duplicate = get_object_or_404(Device, pk=duplicate_pk, location__place=self._place)

                initial['name'] = f"{device_to_duplicate.name}_Dup"
                initial['is_active'] = device_to_duplicate.is_active
                initial['is_lorawan'] = device_to_duplicate.is_lorawan
                initial['is_switchbot'] = device_to_duplicate.is_switchbot
                initial['location'] = device_to_duplicate.location
                initial['device_type'] = device_to_duplicate.device_type
                initial['manufacturer'] = device_to_duplicate.manufacturer
                initial['model'] = device_to_duplicate.model
                initial['device_id'] = '' # Intentionally left blank

            except Device.DoesNotExist:
                pass # Or handle error appropriately

        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self._place
        kwargs['locations'] = self._locations
        kwargs['location'] = self._location # Pass location to form
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['place'] = self._place
        context['locations'] = self._locations

        # Determine the location from the form's initial data if available
        location = self._location
        if not location and 'form' in context:
            location = context['form'].initial.get('location')

        if location:
            context['location'] = location

        # Set a fallback cancel URL
        context['cancel_url'] = self.get_cancel_url()
        return context

    def get_cancel_url(self):
        # If location has a slug, go to location_detail, otherwise go to device_list
        if self._location and hasattr(self._location, 'slug') and self._location.slug:
            return reverse('sensors:location_detail', kwargs={
                'place_slug': self._place.slug,
                'slug': self._location.slug
            })
        else:
            return reverse('sensors:device_list', kwargs={
                'place_slug': self._place.slug
            })

    def get_success_url(self):
        """
        Determine the URL to redirect to on successful form submission.
        """
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.object.location.place.slug,
            'pk': self.object.pk
        })

    def form_valid(self, form):
        # If no location is provided, assign the 'Unassigned' location for the place
        if not form.instance.location:
            form.instance.location = self._place.get_unassigned_location()

        # Save the form to get the object
        self.object = form.save()
        device = self.object

        # Build the message based on whether location is set
        if device.location:
            message = (
                f"Created device <strong>{device.name}</strong> in "
                f"<i class='bi bi-house-gear'></i> {device.location.place.name} > "
                f"<i class='bi bi-geo-alt'></i> {device.location.name}<br>"
            )
        else:
            message = (
                f"Created unassigned device <strong>{device.name}</strong> in "
                f"<i class='bi bi-house-gear'></i> {self._place.name}<br>"
            )

        message += (
            f"<small class='text-muted'>"
            f"Type: {device.device_type or '-'}<br>"
            f"Model: {device.model or '-'}<br>"
            f"Status: {'Active' if device.is_active else 'inactive'}"
            f"</small>"
        )

        # Add inactive warning to message if device is inactive
        # if not device.is_active and self._inactive_help_text:
        #     message += f"<br><small class='text-warning'>{self._inactive_help_text}</small>"

        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data.get('is_active', True) else 'warning'
        })

        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)

    def form_invalid(self, form):
        return super().form_invalid(form)


class DeviceUpdateView(LoginRequiredMixin, PlaceAnnotationMixin, ReferrerMixin, UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'
    object: Device

    def get_queryset(self) -> QuerySet[Device]:
        if not hasattr(self, '_queryset'):
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            base_queryset = super().get_queryset()
            self._queryset = base_queryset.filter(location__place=place).prefetch_related(
                Prefetch(
                    'sensors',
                    queryset=Sensor.objects.order_by('-is_active', Lower('name')),
                    to_attr='sensors_sorted'
                )
            )
        return self._queryset

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place and locations
        self._place = self.get_place()
        self._locations = get_annotated_locations(self._place)

        # Default inactive_help_text to None
        self._inactive_help_text = None
        self._sensors_active = []

        try:
            # Try to get the device if we're updating
            device = self.get_object()
            location = device.location

            # Get help text based on device active state and its location
            self._inactive_help_text = self.get_device_inactive_help_text(device, location)

        except Http404:
            # If we can't get the object yet (e.g., in a GET request before the object exists)
            pass

    def get_device_inactive_help_text(self, device, location=None):
        """
        Generate help text for device inactive status.

        Args:
            device: The device object
            location: The device's location (optional)

        Returns:
            str: help_text HTML string with warning message or None
        """
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self._place
        kwargs['locations'] = self._locations
        kwargs['inactive_help_text'] = self._inactive_help_text
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['place'] = self._place
        device = self.get_object()

        # Add sensors to context
        if hasattr(device, 'sensors_sorted'):
            context['sensors'] = device.sensors_sorted

        # Add location to context
        if device.location:
            context['location'] = get_annotated_locations(self._place).get(pk=device.location.pk)

        return context

    def form_valid(self, form):
        # Store original values before save
        original_is_active = self.object.is_active
        original_location = self.object.location

        # Save the form but don't commit yet to check changes
        device = form.save(commit=False)

        # Retrieve the place from the setup method
        place = self._place

        # Handle the case where location is cleared (set to None)
        if 'location' in form.changed_data and form.cleaned_data['location'] is None:
            device.location = place.get_unassigned_location()

        # If location is not cleared, or it's a new location, set it
        elif 'location' in form.cleaned_data and form.cleaned_data['location']:
            device.location = form.cleaned_data['location']

        # Now, save the device with all changes
        device.save()
        self.object = device  # Update the view's object

        # Check if the location has changed and update toast message
        new_location = self.object.location
        location_changed = original_location != new_location
        status_changed = original_is_active != self.object.is_active

        toast_message = self.construct_toast_message(
            form,
            status_changed,
            location_changed,
            original_location,
            form.changed_data
        )

        setattr(self.request, 'toast_message', toast_message)

        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        return super().form_invalid(form)

    def construct_toast_message(self, form, status_changed, location_changed, original_location, changed_data):
        device = self.object
        message_parts = [f"Updated device <strong>{device.name}</strong>"]
        details = []

        # List of fields to check for changes
        fields_to_check = ['name', 'model', 'manufacturer', 'device_id']

        for field in fields_to_check:
            if field in changed_data:
                old_value = form.initial.get(field, 'N/A')
                new_value = form.cleaned_data.get(field, 'N/A')
                details.append(f"{field.replace('_', ' ').capitalize()}: {old_value} &rarr; {new_value}")

        if location_changed:
            if device.location and device.location.slug != 'unassigned-devices':
                details.append(f"Moved to <i class='bi bi-geo-alt'></i> {device.location.name}")
            else:
                details.append("Moved to <i class='bi bi-question-circle'></i> Unassigned")

        if status_changed:
            status_text = "set to <strong class='text-success'>Active</strong>" if device.is_active else "set to <strong class='text-danger'>inactive</strong>"
            details.append(f"Status {status_text}")

        if not details:
            details.append("No changes detected.")

        message_parts.append("<br><small class='text-muted'>" + ", ".join(details) + "</small>")

        return {
            'message': "".join(message_parts),
            'type': 'success'
        }

class DeviceMoveLocationView(LoginRequiredMixin, View):
    """
    API View to move a device to a new location.
    """
    def get(self, request, place_slug, pk):
        device = get_object_or_404(Device, pk=pk, location__place__slug=place_slug)
        place = device.location.place
        locations = place.locations.exclude(slug='unassigned-devices').order_by('name')

        context = {
            'device': device,
            'place': place,
            'locations': locations,
        }
        return render(request, 'sensors/device_move_modal.html', context)

    def post(self, request, place_slug, pk):
        ic("DeviceMoveLocationView: POST request received.")
        try:
            ic(f"Moving device_id {pk} in place {place_slug}")
            device = get_object_or_404(Device, pk=pk, location__place__slug=place_slug)
            ic(device)

            # HTMX with hx-vals sends data as form-encoded, in request.POST
            ic("Request POST data:", request.POST)
            new_location_id = request.POST.get('location_id')
            make_active = request.POST.get('make_active')

            ic(f"New Location ID from POST: {new_location_id}")
            ic(f"Make active flag: {make_active}")

            if not new_location_id:
                ic("Error: Location ID not found in POST data.")
                return JsonResponse({'error': 'Location ID is required.'}, status=400)

            new_location = get_object_or_404(Location, pk=new_location_id, place__slug=place_slug)
            ic(new_location)

            old_location = device.location
            ic(old_location)

            device.location = new_location
            device.save(update_fields=['location']) # Save location change first
            ic("Device location updated.")

            # If the 'make_active' checkbox was checked, update the active status
            if make_active:
                device.is_active = True
                device.save(update_fields=['is_active'])
                # Also activate all sensors associated with this device
                device.sensors.all().update(is_active=True)
                ic(f"Set device '{device.name}' and its sensors to active.")

            place = get_object_or_404(Place, slug=place_slug)
            place_counts = get_place_counts(place)
            ic(place_counts)

            # Recalculate counts AFTER all changes are saved
            old_location_active_count = old_location.devices.filter(is_active=True).count()
            new_location_active_count = new_location.devices.filter(is_active=True).count()
            ic(f"Old location active count: {old_location_active_count}")
            ic(f"New location active count: {new_location_active_count}")

            response_data = {
                'success': True,
                'message': f"Moved '{device.name}' to '{new_location.name}'.",
                'old_location_id': old_location.id,
                'new_location_id': new_location.id,
                'old_location_active_count': old_location_active_count,
                'new_location_active_count': new_location_active_count,
                'place_counts': place_counts
            }
            ic(response_data)

            return JsonResponse(response_data)
        except Exception as e:
            ic(f"Error in DeviceMoveLocationView: {e}")
            return JsonResponse({'error': str(e)}, status=500)

class DeviceDeleteView(LoginRequiredMixin, PlaceAnnotationMixin, DeleteView):
    model = Device
    template_name = 'sensors/device_confirm_delete.html'
    object: Device

    def get_queryset(self) -> QuerySet[Device]:
        if not hasattr(self, '_queryset'):
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            base_queryset = super().get_queryset()
            self._queryset = base_queryset.filter(location__place=place)
        return self._queryset

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place
        self._place = self.get_place()

        # Create inactive help text to be used in form and toast messages
        try:
            device = self.get_object()
        except Http404:
            device = None
            # ic(f"Error in DeviceDeleteView.setup: {str(e)}")

        if device and device.location and not device.location.is_active:
            self._inactive_help_text = mark_safe(
                    '<i class="bi bi-exclamation-triangle me-2"></i>'
                    f'This device is inactive because Location "{device.location.name}" is inactive.'
                )
        else:
            self._inactive_help_text = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add place to context for template
        context['place'] = self._place

        # Get the device's location
        device = self.get_object()
        if device and hasattr(device, 'location'):
            context['location'] = device.location

        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.headers.get('HX-Request'):
            context = self.get_context_data(object=self.object)
            return render(request, 'sensors/device_confirm_delete_modal.html', context)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        device = self.object
        place = self._place
        location = device.location

        # Before we delete the device, store its data
        device_data = {
            'name': device.name,
            'is_active': device.is_active,
            'device_type': device.device_type.name if device.device_type else '',
            'icon': device.device_type.icon if device.device_type else 'bi-hdd',
            'model': device.model or '',
            'manufacturer': device.manufacturer or '',
            'device_id': device.device_id or ''
        }

        # Get active sensors before deletion
        active_sensors = device.sensors.filter(is_active=True)
        sensors_info = [sensor.name for sensor in active_sensors]

        message = (
            f"Deleted device <strong>{device_data['name']}</strong> from "
            f"<i class='bi bi-diagram-3'></i> {location.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {device_data['device_type']}<br>"
            f"Model: {device_data['model']}<br>"
            f"Manufacturer: {device_data['manufacturer']}<br>"
            f"ID: {device_data['device_id']}<br>"
            f"Active: {'Yes' if device.is_active else 'No'}"
        )

        if sensors_info:
            message += "<br>Affected active sensors:<ul class='mb-0'>"
            for sensor_name in sensors_info:
                message += f"<li>{sensor_name}</li>"
            message += "</ul>"

        message += "</small>"

        # Create toast message with device data
        request.toast_message = {
            'message': message,
            'type': 'warning'
        }

        # Delete the device
        device.delete()

        # Get the success URL
        success_url = self.get_success_url()

        # Handle HTMX request
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=200)
            response['HX-Redirect'] = success_url
            return response

        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return reverse('sensors:place_detail',
                      kwargs={'place_slug': self._place.slug})

@login_required
def fetch_switchbot_reading(request, place_slug, pk):
    """
    View to fetch the latest reading for a SwitchBot device.
    """
    device = get_object_or_404(Device, pk=pk, location__place__slug=place_slug)

    if not device.is_switchbot or not device.device_id:
        messages.error(request, f"Device '{device.name}' is not a configured SwitchBot device.")
        return redirect(device.get_absolute_url())

    try:
        status_response = get_status(device.device_id)
        if status_response.get('statusCode') != 100:
            raise Exception(f"API error: {status_response.get('message', 'Unknown error')}")

        body = status_response.get('body', {})
        readings_found = 0

        # Mapping from API key to SensorType name and the value
        reading_map = {
            'temperature': ('Temperature', body.get('temperature')),
            'humidity': ('Humidity', body.get('humidity')),
            'battery': ('Battery', body.get('battery')),
        }

        for api_key, (sensor_type_name, value) in reading_map.items():
            if value is not None:
                try:
                    sensor = device.sensors.get(sensor_type__name=sensor_type_name)
                    # Create a historical reading
                    SensorReading.objects.create(sensor=sensor, value=value)
                    # Update the cached current reading on the sensor
                    sensor.cached_reading_value = value
                    sensor.cached_reading_timestamp = timezone.now()
                    sensor.save(update_fields=['cached_reading_value', 'cached_reading_timestamp'])
                    readings_found += 1
                except Sensor.DoesNotExist:
                    # This sensor type is not set up for this device, so we skip it.
                    pass

        if readings_found > 0:
            messages.success(request, f"Successfully fetched {readings_found} new reading(s) for {device.name}.")
        else:
            messages.info(request, f"No new readings were available from the API for {device.name}.")

    except Exception as e:
        messages.error(request, f"Failed to fetch readings for {device.name}: {e}")

    return redirect(device.get_absolute_url())
