from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, FormView
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
from .sensor_forms import SensorForm, LoRaWANSensorForm, DeviceDeleteForm
from ..utils import get_sensor_readings, generate_sparkline, get_latest_influx_reading, update_sensor_live_value
from ..decorators import log_execution_time
from ..services.switchbot_service import SwitchBotService

from django.contrib.auth.decorators import login_required
from django.contrib import messages

# logger = logging.getLogger(__name__) # No longer needed

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
                        queryset=Sensor.objects.select_related('sensor_type', 'sensor_type__unit')
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

        # Update live values for all sensors being displayed
        if context['sensors']:
            for sensor in context['sensors']:
                update_sensor_live_value(sensor, force_update=False)

        # --- Hub Device for SwitchBot ---
        if device.is_switchbot and device.hub_id:
            try:
                hub_device = Device.objects.get(device_id=device.hub_id, location__place=self._place)
                context['hub_device'] = hub_device
            except Device.DoesNotExist:
                context['hub_device'] = None

        # --- Smart Data Fetching for Sensors ---
        # This is now handled above before context is returned
        # self.fetch_live_data_for_sensors(context['sensors'])

        # --- SwitchBot Missing Sensor Detection ---
        # This is now handled by an HTMX call triggered by the user
        # if device.is_switchbot and device.device_id and self._place.switchbot_enable:
        #     if self._place.switchbot_token and self._place.switchbot_secret:
        #         try:
        #             status_data = get_status(device.device_id, self._place.switchbot_token, self._place.switchbot_secret)
        #             if status_data.get('statusCode') == 100:
        #                 body = status_data.get('body', {})

        #                 existing_sensor_types = set(
        #                     s.lower() for s in device.sensors.select_related('sensor_type')
        #                                   .filter(sensor_type__name__isnull=False)
        #                                   .values_list('sensor_type__name', flat=True)
        #                 )
        #                 ic(f"[{device.name}] Existing sensor types:", existing_sensor_types)

        #                 excluded_keys = {'version', 'deviceid', 'devicetype', 'hubdeviceid'}

        #                 missing_sensors = []
        #                 for key, value in body.items():
        #                     if key.lower() in excluded_keys:
        #                         continue

        #                     # Translate the API key to our internal, standardized name
        #                     standardized_name = SWITCHBOT_KEY_MAP.get(key)
        #                     ic(f"[{device.name}] Checking API key: '{key}' -> Standardized: '{standardized_name}'")

        #                     if standardized_name and standardized_name.lower() not in existing_sensor_types:
        #                         ic(f"[{device.name}] Found missing sensor: '{standardized_name}'")
        #                         missing_sensors.append({
        #                             'name': key, # The original key from the API
        #                             'display_name': standardized_name, # Our internal name
        #                             'value': value,
        #                         })

        #                 ic(f"[{device.name}] Final list of missing sensors:", missing_sensors)
        #                 context['missing_switchbot_sensors'] = missing_sensors
        #                 context['switchbot_inspect_data'] = json.dumps(status_data, indent=2)

        #         except Exception as e:
        #             ic(f"Failed to get SwitchBot status for device detail view: {e}")
        #             context['switchbot_error'] = f"Failed to get SwitchBot status: {e}"
        #     else:
        #         context['switchbot_error'] = "SwitchBot credentials are not configured for this place."


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
        DEPRECATED: Logic moved directly into get_context_data.
        """
        # The logic to group SwitchBot calls is now handled inside the util,
        # or accepted as a trade-off for simplicity in the live-value-per-sensor context.
        # For a full device page refresh, this is still efficient enough.
        for sensor in sensors:
            update_sensor_live_value(sensor)

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
        device = get_object_or_404(
            Device.objects.prefetch_related('sensors__sensor_type'),
            pk=pk,
            location__place__slug=place_slug
        )
        place = device.location.place
        locations = place.locations.exclude(pk=device.location.pk).exclude(slug='unassigned-devices').annotate(
            active_device_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_device_count=Count('devices', filter=Q(devices__is_active=False)),
        ).order_by('name')

        context = {
            'device': device,
            'place': place,
            'locations': locations,
        }
        return render(request, 'sensors/device_move_modal.html', context)

    def post(self, request, place_slug, pk):
        try:
            device = get_object_or_404(
                Device.objects.annotate(
                    sensors_active_count=Count('sensors', filter=Q(sensors__is_active=True)),
                    sensors_inactive_count=Count('sensors', filter=Q(sensors__is_active=False))
                ),
                pk=pk,
                location__place__slug=place_slug
            )

            new_location_id = request.POST.get('location_id')
            make_active = request.POST.get('make_active')

            if not new_location_id:
                return JsonResponse({'error': 'Location ID is required.'}, status=400)

            new_location = get_object_or_404(Location, pk=new_location_id, place__slug=place_slug)

            device.location = new_location

            if make_active:
                device.is_active = True
                device.sensors.all().update(is_active=True)

            device.save()

            messages.success(request, f"Moved '{device.name}' to '{new_location.name}'.")

            # Redirect to the page that initiated the request to force a full reload.
            # Fallback to the main device list for the place if the header is not present.
            redirect_url = request.headers.get('HX-Current-URL', reverse('sensors:device_list', kwargs={'place_slug': place_slug}))

            response = HttpResponse(status=204)
            response['HX-Redirect'] = redirect_url
            return response

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class DeviceDeleteView(LoginRequiredMixin, PlaceAnnotationMixin, DeleteView):
    model = Device
    template_name = 'sensors/device_confirm_delete.html'
    context_object_name = 'object'

    def get_queryset(self):
        # Ensure we are only touching devices within the specified place
        return Device.objects.filter(location__place__slug=self.kwargs['place_slug'])

    def get_object(self, queryset=None):
        # Use pk from URL to fetch the specific device
        return get_object_or_404(self.get_queryset(), pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = self._place
        # The form is needed for confirmation, but DeleteView can handle it.
        # We can add a simple form if needed, or rely on a POST request.
        # For now, let's keep it simple.
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        if request.htmx:
            return render(request, 'sensors/partials/device_confirm_delete_modal.html', context)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        device_name = self.object.name
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(self.request, f"Device '{device_name}' and all its sensors have been deleted.")

        if self.request.htmx:
            response = HttpResponse(status=204)
            response['HX-Redirect'] = success_url
            return response
        return redirect(success_url)

    def get_success_url(self):
        return reverse('sensors:device_list', kwargs={'place_slug': self.kwargs['place_slug']})
