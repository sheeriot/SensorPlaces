from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.utils.decorators import method_decorator

from django.db.models import OuterRef, Subquery, Count, Min, Max, Prefetch, Q
from django.db.models.functions import Lower

from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.http import JsonResponse, HttpResponseRedirect, HttpRequest, HttpResponse

from django.utils import timezone
from django.utils.safestring import mark_safe

from ..models import Device, Sensor, SensorReading, Place, Location
from .mixins import PlaceAnnotationMixin, ReferrerMixin
from .sensor_forms import SensorForm, LoRaWANSensorForm
from .views_fun import get_annotated_locations, get_live_counts_context
from ..decorators import log_execution_time
from ..utils import get_latest_influx_reading, update_sensor_live_value

from datetime import datetime, timedelta, timezone as dt_timezone

from django.template.loader import render_to_string

from django.views.decorators.http import require_POST
import json
from django.views import View

from icecream import ic

def parse_date_to_local_tz(date_str):
    """
    Parses a YYYY-MM-DD string into a timezone-aware datetime object
    representing the beginning of that day in the user's current timezone.
    """
    dt_naive = datetime.strptime(date_str, '%Y-%m-%d')
    # timezone.make_aware will use the currently activated timezone
    # thanks to the TimezoneMiddleware
    return timezone.make_aware(dt_naive)

class SensorListView(LoginRequiredMixin, PlaceAnnotationMixin, ListView):
    model = Location
    context_object_name = 'locations'
    template_name = 'sensors/sensor_list.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Check if we're filtering by device
        device_pk = self.kwargs.get('device_pk')
        if device_pk:
            device_qs = Device.objects.annotate(
                active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)),
                inactive_sensors_count=Count('sensors', filter=Q(sensors__is_active=False))
            ).prefetch_related(
                Prefetch(
                    'sensors',
                    queryset=Sensor.objects.order_by('-is_active', Lower('name')),
                    to_attr='sensors_sorted'
                )
            )
            self._device = get_object_or_404(device_qs, pk=device_pk, location__place=self._place)
        else:
            self._device = None

    def get_queryset(self):
        """
        Get locations for the place, with devices and sensors prefetched
        to allow for grouping in the template.
        """
        sensors_prefetch = Prefetch(
            'sensors',
            queryset=Sensor.objects.order_by('-is_active', Lower('name')),
            to_attr='sensors_sorted'
        )

        devices_prefetch = Prefetch(
            'devices',
            queryset=Device.objects.select_related('device_type').annotate(
                sensors_active_count=Count('sensors', filter=Q(sensors__is_active=True)),
                sensors_inactive_count=Count('sensors', filter=Q(sensors__is_active=False))
            ).prefetch_related(sensors_prefetch).order_by('-is_active', Lower('name')),
            to_attr='devices_sorted'
        )

        return get_annotated_locations(self._place).prefetch_related(devices_prefetch)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        
        # Add hide_inactive state from GET param or cookie
        hide_inactive_param = self.request.GET.get('hide_inactive')
        if hide_inactive_param is not None:
            context['hide_inactive'] = hide_inactive_param.lower() == 'true'
        else:
            hide_inactive_cookie = self.request.COOKIES.get('hideInactive_sensor', 'false')
            context['hide_inactive'] = hide_inactive_cookie.lower() == 'true'

        # If we're looking at a specific device's sensors, add it to context
        if hasattr(self, '_device') and self._device:
            context['device'] = self._device
            context['location'] = self._device.location
            context['sensors'] = self._device.sensors_sorted
        
        # Add live counts to context
        context.update(get_live_counts_context(self._place))
        
        return context

def parse_date_to_local_tz(date_str):
    """
    Parses a YYYY-MM-DD string into a timezone-aware datetime object
    representing the beginning of that day in the user's current timezone.
    """
    dt_naive = datetime.strptime(date_str, '%Y-%m-%d')
    # timezone.make_aware will use the currently activated timezone
    # thanks to the TimezoneMiddleware
    return timezone.make_aware(dt_naive)


def get_date_range(delta_str):
    """
    Helper to get start and end dates based on a delta string (e.g., '1d', '2h').
    Returns a tuple (start_date, end_date).
    """
    end_date = timezone.now()
    if delta_str.endswith('d'):
        days = int(delta_str[:-1])
        start_date = end_date - timedelta(days=days)
    elif delta_str.endswith('h'):
        hours = int(delta_str[:-1])
        start_date = end_date - timedelta(hours=hours)
    else:
        # Default or error case
        start_date = end_date - timedelta(days=7)
    return start_date, end_date


def _parse_date_range_from_params(params):
    """
    Parses date range parameters from a dictionary (e.g., request.GET or view.kwargs)
    and returns timezone-aware datetime objects and their ISO string representations.
    """
    start_date_str = params.get('start') or params.get('start_date')
    end_date_str = params.get('end') or params.get('end_date')
    delta_str = params.get('delta')

    start_date, end_date = None, None
    start_date_iso, end_date_iso = None, None

    if start_date_str and end_date_str:
        # These are now full ISO strings from the client
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))

        start_date_iso = start_date.isoformat()
        end_date_iso = end_date.isoformat()
    elif delta_str:
        start_date, end_date = get_date_range(delta_str)
        start_date_iso = start_date.isoformat()
        end_date_iso = end_date.isoformat()

    return start_date, end_date, start_date_iso, end_date_iso, delta_str


@method_decorator(log_execution_time, name='dispatch')
class SensorDetailView(LoginRequiredMixin, PlaceAnnotationMixin, DetailView):
    model = Sensor
    context_object_name = 'sensor'
    template_name = 'sensors/sensor_detail.html'
    
    def get_queryset(self):
        """Get sensors for this place with annotations."""
        # Use the cached place
        base_queryset = super().get_queryset()
        
        # Filter sensors for this place and prefetch related fields
        queryset = base_queryset.filter(
            device__location__place=self._place
        ).select_related(
            'device',
            'device__location',
            'device__location__place',
        )
        
        # Get the last reading if it exists
        last_reading = SensorReading.objects.filter(
            sensor=OuterRef('pk')
        ).order_by('-timestamp')
        
        # Annotate with the last reading value and timestamp
        return queryset.annotate(
            last_value=Subquery(
                last_reading.values('value')[:1]
            ),
            last_reading_time=Subquery(
                last_reading.values('timestamp')[:1]
            ))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        context['absolute_url'] = self.request.build_absolute_uri()
        
        # Add device and location to context
        sensor = self.get_object()

        # Ensure the live value is fresh before rendering the detail card
        if sensor.data_type and sensor.data_type.startswith('INFLUX'):
            update_sensor_live_value(sensor)

        device_qs = Device.objects.annotate(
            active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)),
            inactive_sensors_count=Count('sensors', filter=Q(sensors__is_active=False))
        )
        device = get_object_or_404(device_qs, pk=sensor.device.pk)

        context['device'] = device
        context['location'] = device.location
        
        # Add all sensors for the device to the context
        context['sensors'] = Sensor.objects.filter(device=device).order_by(Lower('name'))
        context['narrow_view'] = True
        
        # Use the new helper to parse date range from URL kwargs
        start_date, end_date, start_date_iso, end_date_iso, delta = _parse_date_range_from_params(self.kwargs)

        context['start_date_iso'] = start_date_iso
        context['end_date_iso'] = end_date_iso
        context['delta'] = delta
        
        # The readings for the graph ARE filtered by the date range
        # This part is now handled by the async graph card view for LoRaWAN,
        # but we keep it for other sensor types.
        if not sensor.device.is_lorawan:
            graph_readings_qs = SensorReading.objects.filter(sensor=sensor)
            if start_date and end_date:
                graph_readings_qs = graph_readings_qs.filter(timestamp__gte=start_date, timestamp__lt=end_date)
            context['readings'] = graph_readings_qs.order_by('timestamp')

        # Overall statistics are NOT filtered by the date range.
        # This is also moved to the async view for LoRaWAN sensors.
        if not sensor.device.is_lorawan:
            all_readings_qs = SensorReading.objects.filter(sensor=sensor)
            stats = all_readings_qs.aggregate(
                first_reading=Min('timestamp'),
                last_reading=Max('timestamp'),
                reading_count=Count('id')
            )
            context['reading_stats'] = stats
        
        # Generate sparkline based on the filtered graph data
        if not sensor.device.is_lorawan:
            timestamps = [reading.timestamp for reading in context.get('readings', [])]
            # context['sparkline_image'] = generate_sparkline(timestamps) # Removed as per edit hint
        
        # Add locations for the place_nav_card
        context['locations'] = get_annotated_locations(self._place)
        
        return context


class SensorLiveValueView(LoginRequiredMixin, View):
    """
    A view that fetches the live value for a sensor and returns it as JSON.
    """
    def get(self, request, *args, **kwargs):
        sensor_pk = self.kwargs.get('pk')
        try:
            sensor = get_object_or_404(Sensor, pk=sensor_pk)
            update_sensor_live_value(sensor)

            if sensor.cached_reading_value is not None:
                response_data = {
                    'status': 'success',
                    'value': sensor.cached_reading_value,
                    'timestamp': sensor.cached_reading_timestamp.isoformat() if sensor.cached_reading_timestamp else None,
                    'unit_symbol': sensor.effective_unit.symbol if sensor.effective_unit else '',
                    'decimal_places': sensor.effective_decimal_places
                }
                return JsonResponse(response_data)
            else:
                return JsonResponse({'status': 'no_reading', 'message': 'No current reading available.'})

        except Sensor.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Sensor not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class SensorGraphCardView(LoginRequiredMixin, PlaceAnnotationMixin, DetailView):
    """
    A view that renders only the sensor graph card, intended to be loaded asynchronously.
    """
    model = Sensor
    template_name = 'sensors/includes/sensor_graph_card.html'
    context_object_name = 'sensor'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sensor = self.get_object()

        # Update the live value before rendering the card
        if sensor.data_type and sensor.data_type.startswith('INFLUX'):
            update_sensor_live_value(sensor)

        # Add device and location to context
        context['device'] = sensor.device
        context['location'] = sensor.device.location
        
        # Pass the sensor's live value to the template
        context['live_value'] = sensor.cached_reading_value
        context['live_timestamp'] = sensor.cached_reading_timestamp

        # We no longer fetch stats on initial load.
        # The date range is set by the JS, so we don't need to parse it here either.
        context['reading_stats'] = {}
        
        return context


class SensorCreateView(LoginRequiredMixin, PlaceAnnotationMixin, ReferrerMixin, CreateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'
    object: Sensor

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place, locations, device, location
        self._place = self.get_place()
        self._locations = get_annotated_locations(self._place)
        try:
            device_qs = Device.objects.annotate(
                active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)),
                inactive_sensors_count=Count('sensors', filter=Q(sensors__is_active=False))
            )
            self._device = get_object_or_404(device_qs, pk=self.kwargs.get('device_pk', None))
        except Exception as e:
            # ic(f"Error getting device: {str(e)}")
            pass

    def get_sensor_inactive_help_text(self, sensor, device=None):
        """
        Generate help text for sensor inactive status.
        
        Args:
            sensor: The sensor object
            device: The sensor's device (optional)
            
        Returns:
            str: HTML string with warning message or None
        """
        inactive_help_text = None
            
        # If device is inactive, create help text about that
        if device and not device.is_active:
            # For existing sensors, check if active when they shouldn't be
            if sensor and hasattr(sensor, 'is_active') and sensor.is_active and hasattr(sensor, 'pk') and sensor.pk:
                # Fix the inconsistency - set sensor to inactive
                sensor.is_active = False
                sensor.save()
                
                # Just log the inconsistency with ic
                # ic(f"Fixed inconsistency: Sensor {sensor.id} ({sensor.name}) was active "
                #    f"but its Device {device.id} ({device.name}) is inactive.")
            
            # Standard message for inactive device
            inactive_help_text = mark_safe(
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                f'Sensor cannot be active because Device "{device.name}" is inactive.'
            )
        # If sensor is active, create help text about deactivation
        elif sensor and sensor.is_active:
            inactive_help_text = mark_safe(
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                'If deactivated, this sensor will no longer collect data and readings will not be available.'
            )
        
        return inactive_help_text

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self._place
        kwargs['device'] = self._device
        
        # Set is_active based on device status
        if self._device:
            kwargs.setdefault('initial', {})['is_active'] = self._device.is_active
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        # Place is already in context from PlaceAnnotationMixin
        
        # Add device and location data
        if hasattr(self, '_device') and self._device:
            context['device'] = self._device
            context['location'] = self._device.location
        
        return context

    def get_default_success_url(self):
        # Fallback if no referrer is available
        if hasattr(self, '_device') and self._device:
            return reverse('sensors:device_detail', kwargs={
                'place_slug': self._place.slug,
                'pk': self._device.pk
            })
        else:
            return reverse('sensors:place_detail', kwargs={
                'place_slug': self._place.slug
            })

    def get_cancel_url(self):
        """Returns the URL to the device's detail page."""
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self._place.slug,
            'pk': self._device.pk
        })

    def form_valid(self, form):
        
        # Ensure is_active is set correctly based on device status
        if self._device.is_active and not form.instance.is_active:
            # If device is active but form has inactive sensor, respect the form value
            pass
        elif not self._device.is_active:
            # If device is inactive, sensor must be inactive
            form.instance.is_active = False
        else:
            # If device is active and no explicit choice, make sensor active
            form.instance.is_active = True
        
        # Save the form to get the object
        self.object = form.save()
        sensor = self.object

        
        message = (
            f"Created sensor <strong>{sensor.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {self._place.name} > "
            f"<i class='bi bi-geo-alt'></i> {self._device.location.name} > "
            f"<i class='bi bi-hdd-rack'></i> {self._device.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {sensor.sensor_type.name if sensor.sensor_type else 'N/A'}<br>"
            f"Unit: {sensor.effective_unit}<br>"
            f"Data Type: {sensor.get_effective_data_type_display}<br>"
            f"Status: {'Active' if sensor.is_active else 'inactive'}"
            f"</small>"
        )
        
        # Add inactive warning to message if sensor is inactive
        inactive_help_text = self.get_sensor_inactive_help_text(sensor, self._device)
        if not sensor.is_active and inactive_help_text:
            message += f"<br><small class='text-warning'>{inactive_help_text}</small>"
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if sensor.is_active else 'warning'
        })
        
        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)


class LoRaWANSensorCreateView(LoginRequiredMixin, PlaceAnnotationMixin, ReferrerMixin, CreateView):
    model = Sensor
    form_class = LoRaWANSensorForm
    template_name = 'sensors/lorawan_sensor_form.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.place = self.get_place()
        self.device = get_object_or_404(Device, pk=self.kwargs['device_pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self.place
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = self.place
        context['device'] = self.device
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.device = self.device
        self.object.save()
        return super().form_valid(form)

    def get_default_success_url(self):
        return reverse('sensors:device_detail', kwargs={'place_slug': self.place.slug, 'pk': self.device.pk})


class SensorUpdateView(LoginRequiredMixin, PlaceAnnotationMixin, ReferrerMixin, UpdateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'
    object: Sensor

    def get_queryset(self):
        """
        Optimize the queryset to pre-fetch related objects and avoid N+1 queries.
        """
        return super().get_queryset().select_related(
            'device',
            'device__location',
            'sensor_type',
            'sensor_type__default_unit',
            'unit'
        )

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place
        self._place = self.get_place()
        self._locations = get_annotated_locations(self._place)
        
        # Default inactive_help_text to None
        self._inactive_help_text = None
        self._device = None
        
        try:
            # Try to get the sensor if we're updating
            sensor = self.get_object()
            device_pk = sensor.device.pk
            device_qs = Device.objects.annotate(
                active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)),
                inactive_sensors_count=Count('sensors', filter=Q(sensors__is_active=False))
            )
            self._device = get_object_or_404(device_qs, pk=device_pk)
            
            # Get help text based on sensor active state and its device
            self._inactive_help_text = self.get_sensor_inactive_help_text(sensor, self._device)
            
        except Exception as e:
            # If we can't get the object yet (e.g., in a GET request before the object exists)
            # ic(f"Error in SensorUpdateView.setup: {str(e)}")
            pass
            
    def get_sensor_inactive_help_text(self, sensor, device=None):
        """
        Generate help text for sensor inactive status.
        
        Args:
            sensor: The sensor object
            device: The sensor's device (optional)
            
        Returns:
            str: HTML string with warning message or None
        """
        inactive_help_text = None
        
        if not sensor:
            return None
            
        if not device:
            device = sensor.device
            
        # If device is inactive, create help text about that
        if device and not device.is_active:
            # Check if sensor is active when it shouldn't be
            if sensor and sensor.is_active:
                # Fix the inconsistency - set sensor to inactive
                sensor.is_active = False
                sensor.save()
                
                # Just log the inconsistency with ic
                # ic(f"Fixed inconsistency: Sensor {sensor.pk} ({sensor.name}) was active "
                #    f"but its Device {device.pk} ({device.name}) is inactive.")
            
            # Standard message for inactive device
            inactive_help_text = mark_safe(
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                f'This sensor will be inactive because Device "{device.name}" is inactive.'
            )
        # If sensor is active, create help text about deactivation
        elif sensor and sensor.is_active:
            inactive_help_text = mark_safe(
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                'If deactivated, this sensor will no longer collect data and readings will not be available.'
            )
        
        return inactive_help_text

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'place': self._place,
            'device': self._device,
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Explicitly add the form to the context to solve the crash
        if 'form' not in context:
            context['form'] = self.get_form()
            
        context['model_name'] = 'sensor'
        
        sensor = self.object # Use self.object which is already fetched by UpdateView
        device = sensor.device
        
        # You can still annotate the device if needed for other parts of the template
        # but the primary object relationships are already there.
        device_annotated = Device.objects.annotate(
            active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)),
            inactive_sensors_count=Count('sensors', filter=Q(sensors__is_active=False))
        ).get(pk=device.pk)

        context['device'] = device_annotated
        context['location'] = device_annotated.location
        
        return context

    def get_default_success_url(self):
        """
        Redirect to the referrer URL from the form's cleaned data if it exists,
        otherwise fall back to the sensor's detail page.
        """
        return reverse('sensors:sensor_detail', kwargs={
            'place_slug': self._place.slug,
            'pk': self.object.pk
        })

    def form_valid(self, form):

        
        # Store original values before save
        sensor = self.get_object()
        self._original_values = {
            'name': sensor.name,
            'is_active': sensor.is_active,
            'device': sensor.device,
            'sensor_type': sensor.sensor_type,
            'data_type': sensor.data_type,
            'unit_id': sensor.unit_id
        }
        
        # Ensure is_active is set correctly based on device status
        if not self._device.is_active and form.instance.is_active:
            # If device is inactive, sensor must be inactive
            form.instance.is_active = False
        
        # Save the form
        self.object = form.save()
        sensor = self.object
        device = sensor.device
        location = device.location
        place = location.place
        
        changes = []
        
        if hasattr(self, '_original_values'):
            if self._original_values['name'] != sensor.name:
                changes.append(f"name: {self._original_values['name']} → {sensor.name}")
            if self._original_values['is_active'] != sensor.is_active:
                changes.append(f"active: {self._original_values['is_active']} → {sensor.is_active}")
            if self._original_values['device'] != sensor.device:
                changes.append(f"device: {self._original_values['device'].name} → {sensor.device.name}")
            if self._original_values['sensor_type'] != sensor.sensor_type:
                changes.append(f"type: {self._original_values['sensor_type']} → {sensor.sensor_type}")
            if 'data_type' in self._original_values and self._original_values['data_type'] != sensor.effective_data_type:
                changes.append(f"data type: {self._original_values['data_type']} → {sensor.get_effective_data_type_display}")
            if 'unit_id' in self._original_values and self._original_values['unit_id'] != (sensor.effective_unit.id if sensor.effective_unit else None):
                # Need to import Unit at the top
                from ..models import Unit
                original_unit_pk = self._original_values['unit_id']
                original_unit = Unit.objects.get(pk=original_unit_pk) if original_unit_pk else "None"
                changes.append(f"unit: {original_unit} → {sensor.effective_unit}")

        message = (
            f"Updated sensor <strong>{sensor.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name} > "
            f"<i class='bi bi-hdd-rack'></i> {device.name}"
        )
        
        if changes:
            message += f"<br><small class='text-muted'>Changes: {', '.join(changes)}</small>"
        
        # Add inactive warning to message if sensor is inactive
        if not sensor.is_active and self._inactive_help_text:
            message += f"<br><small class='text-warning'>{self._inactive_help_text}</small>"
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if sensor.is_active else 'warning',
            'place_id': place.pk  # Use place_id instead of place object
        })
        
        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)

class SensorDeleteView(LoginRequiredMixin, PlaceAnnotationMixin, DeleteView):
    model = Sensor
    template_name = 'sensors/sensor_confirm_delete.html'
    object: Sensor

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place
        self._place = self.get_place()
        
        # Create inactive help text to be used in form and toast messages
        try:
            sensor = self.get_object()
            device = sensor.device
            
            if device and not device.is_active:
                self._inactive_help_text = mark_safe(
                    '<i class="bi bi-exclamation-triangle me-2"></i>'
                    f'This sensor is inactive because Device "{device.name}" is inactive.'
                )
            else:
                self._inactive_help_text = None
        except Exception as e:
            self._inactive_help_text = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sensor = self.get_object()
        device = sensor.device
        
        # Add device and location to context
        context['device'] = device
        context['location'] = device.location
        context['place'] = device.location.place # Pass the place object for breadcrumbs
        # Place is already in context from PlaceAnnotationMixin
        context['model_name'] = 'sensor'
        
        # Add sensor_url for cancel button
        context['sensor_url'] = reverse('sensors:sensor_detail', kwargs={
            'place_slug': self._place.slug,
            'pk': sensor.pk
        })
        
        # Add a fallback cancel URL
        context['cancel_fallback_url'] = reverse('sensors:device_detail', kwargs={
            'place_slug': self._place.slug,
            'pk': device.pk
        })
        
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET requests, checking for HTMX."""
        self.object = self.get_object()
        # If it's an HTMX request, render the modal partial
        if 'HX-Request' in request.headers:
            context = self.get_context_data(object=self.object)
            return render(request, 'sensors/partials/sensor_confirm_delete_modal.html', context)
        
        # Otherwise, render the full page
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        sensor = self.object
        device = sensor.device
        location = device.location
        place = location.place
        
        # Store the IDs BEFORE deleting the object
        sensor_id = sensor.pk
        device_id = device.pk
        sensor_name = sensor.name

        # Delete the sensor
        sensor.delete()
        
        # Create toast message
        message = f"Deleted sensor <strong>{sensor_name}</strong> from {device.name}."
        
        # Set toast message directly on request for middleware
        setattr(request, 'toast_message', {
            'message': message,
            'type': 'warning',
            'place_id': place.pk
        })
        
        # For HTMX requests from the modal, send back an event trigger
        if 'HX-Request' in request.headers:
            response = HttpResponse(status=204) # No Content
            response['HX-Trigger'] = json.dumps({
                'sensorDeleted': {
                    'sensorId': sensor_id,
                    'deviceId': device_id
                }
            })
            return response
            
        # Standard response for non-HTMX requests (fallback)
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        # Fallback success URL
        device = self.object.device
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self._place.slug,
            'pk': device.pk
        })

class SensorReadingListView(LoginRequiredMixin, PlaceAnnotationMixin, ListView):
    model = SensorReading
    context_object_name = 'readings'
    template_name = 'sensors/sensor_reading_list.html'
    paginate_by = 20

    def get_queryset(self):
        sensor = get_object_or_404(Sensor, pk=self.kwargs['sensor_pk'])
        queryset = super().get_queryset().filter(sensor=sensor)

        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__range=[start_date, end_date])
            except ValueError:
                # Use toast_message instead of messages
                setattr(self.request, 'toast_message', {
                    'message': 'Invalid date format. Please use YYYY-MM-DD.',
                    'type': 'error'
                })
        elif start_date or end_date:
            # Use toast_message instead of messages
            setattr(self.request, 'toast_message', {
                'message': 'Both start_date and end_date must be provided.',
                'type': 'error'
            })

        return queryset.select_related(
            'sensor', 
            'sensor__device', 
            'sensor__device__location', 
            'sensor__device__location__place'
        ).order_by('-timestamp')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sensor = get_object_or_404(Sensor, pk=self.kwargs['sensor_pk'])
        context['sensor'] = sensor
        context['device'] = sensor.device
        context['location'] = sensor.device.location
        context['place'] = sensor.device.location.place
        context['model_name'] = 'sensor_reading'

        # Calculate statistics
        readings = context['readings']
        if readings:
            values = [reading.value for reading in readings]
            context['readings_summary'] = {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'first_timestamp': readings[0].timestamp,
                'last_timestamp': readings[-1].timestamp,
                'unit': sensor.unit
            }

        return context

class SensorReadingDetailView(LoginRequiredMixin, PlaceAnnotationMixin, DetailView):
    model = SensorReading
    context_object_name = 'reading'
    template_name = 'sensors/sensor_reading_detail.html'

    def get_queryset(self):
        sensor = get_object_or_404(Sensor, pk=self.kwargs['sensor_pk'])
        return super().get_queryset().filter(sensor=sensor)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reading = self.get_object()
        sensor = reading.sensor
        context['sensor'] = sensor
        context['device'] = sensor.device
        context['location'] = sensor.device.location
        context['place'] = sensor.device.location.place
        context['model_name'] = 'sensor_reading'

        # Get previous and next reading IDs
        readings = list(self.get_queryset())
        current_index = readings.index(reading)
        context['prev_reading_id'] = readings[current_index - 1].id if current_index > 0 else None
        context['next_reading_id'] = readings[current_index + 1].id if current_index < len(readings) - 1 else None

        return context

class SensorReadingCreateView(LoginRequiredMixin, PlaceAnnotationMixin, CreateView):
    model = SensorReading
    fields = ['value', 'timestamp']
    template_name = 'sensors/sensor_reading_form.html'

    def setup(self, request, *args, **kwargs):
        """Cache common values during view setup"""
        super().setup(request, *args, **kwargs)
        # Place is already set by PlaceAnnotationMixin
        
        # Get and cache the sensor
        sensor_pk = self.kwargs.get('sensor_pk')
        if sensor_pk:
            self._sensor = get_object_or_404(
                Sensor.objects.select_related(
                    'device',
                    'device__location'
                ),
                pk=sensor_pk,
                device__location__place=self._place
            )
        else:
            self._sensor = None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Set initial timestamp to now
        kwargs['initial'] = kwargs.get('initial', {})
        kwargs['initial']['timestamp'] = timezone.now()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'model_name': 'sensor_reading',
            # Place is already in context from PlaceAnnotationMixin
            'sensor': self._sensor,
            'device': self._sensor.device if self._sensor else None,
            'location': self._sensor.device.location if self._sensor else None,
        })
        return context

    def form_valid(self, form):
        form.instance.sensor = self._sensor
        response = super().form_valid(form)
        reading = self.object
        sensor = reading.sensor
        device = sensor.device
        location = device.location
        place = location.place
        
        message = (
            f"Created reading for sensor: "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name} > "
            f"<i class='bi bi-hdd-rack'></i> {device.name} > "
            f"<i class='bi bi-thermometer'></i> {sensor.name}<br>"
            f"<small class='text-muted'>"
            f"Value: {reading.value} {sensor.effective_unit or '-'}<br>"
            f"Timestamp: {reading.timestamp}"
            f"</small>"
        )
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success'
        })
        
        return response

    def get_success_url(self):
        return reverse('sensors:sensor_reading_detail', kwargs={
            'place_slug': self._place.slug,
            'sensor_pk': self._sensor.pk,
            'pk': self.object.pk
        })

@method_decorator(csrf_protect, name='dispatch')
@login_required
@csrf_protect
def test_sensor_readings(request, place_slug, sensor_pk):
    """Test sensor readings from InfluxDB for the last 60 minutes"""
    sensor = get_object_or_404(Sensor, 
                              pk=sensor_pk,
                              device__location__place__slug=place_slug)
    
    # Only test InfluxDB sensors
    if sensor.data_type != 'INFLUX':
        return JsonResponse({
            'status': 'error',
            'message': 'This sensor does not use InfluxDB as its data source'
        }, status=400)
    
    try:
        # Get readings for the last 60 minutes
        from datetime import timedelta
        from django.utils import timezone
        
        # Get readings for the last hour
        stop = timezone.now()
        start = stop - timedelta(minutes=60)
        
        # readings = get_sensor_readings(sensor=sensor, start=start, stop=stop, limit=100) # Removed as per edit hint
        
        if not readings: # Changed from 'not readings' to 'if not readings'
            return JsonResponse({
                'status': 'warning',
                'message': 'Connection successful but no data found in the last 60 minutes'
            })
        
        # Calculate summary statistics
        values = [reading['value'] for reading in readings]
        summary = {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'first_timestamp': readings[0]['timestamp'],
            'last_timestamp': readings[-1]['timestamp'],
            'unit': sensor.unit
        }
        
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully retrieved {len(readings)} readings',
            'summary': summary,
            'readings': readings[:10]  # Return first 10 readings for display
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to connect to InfluxDB: {str(e)}'
        }, status=500)

@login_required
@log_execution_time
def sensor_readings_api(request: HttpRequest, place_slug: str, pk: int) -> JsonResponse:
    """
    API endpoint to get sensor readings for a given sensor.
    This view now acts as a router. If the sensor is an InfluxDB sensor, it will internally call the logic for that. Otherwise, it will
    query the local PostgreSQL database.
    """
    try:
        sensor = get_object_or_404(
            Sensor,
            pk=pk,
            device__location__place__slug=place_slug
        )

        # If this is an InfluxDB sensor, use the InfluxDB data path.
        if sensor.effective_data_type.startswith('INFLUX'):
            return lorawan_sensor_data_api(request, place_slug, pk)

        # --- The rest of this function is for local DB sensors ---
        
        start_time = timezone.now()
        user_timezone_str = request.GET.get('timezone')
        if user_timezone_str:
            timezone.activate(user_timezone_str)
        
        # Use the new helper to parse date range from GET parameters
        start_date, end_date, start_date_iso, end_date_iso, _ = _parse_date_range_from_params(request.GET)
        ic("Date range from params:", start_date, end_date)

        queryset = SensorReading.objects.filter(sensor=sensor)
        ic("Initial queryset count:", queryset.count())

        if start_date and end_date:
            queryset = queryset.filter(timestamp__gte=start_date, timestamp__lt=end_date)
            ic("Filtered queryset count:", queryset.count())
        else:
            # Default to the last 24 hours if no range is provided, and set dates for response
            end_date = timezone.now()
            start_date = end_date - timedelta(days=1)
            queryset = queryset.filter(timestamp__gte=start_date)

        readings = list(queryset.order_by('timestamp').values('timestamp', 'value'))
        ic("Final number of readings found:", len(readings))
        
        # Format data into the structure expected by the frontend chart
        serializable_data_points = []
        if readings:
            for r in readings:
                serializable_val = float(r['value']) if r['value'] is not None else None
                serializable_data_points.append((r['timestamp'].isoformat(), serializable_val))

        end_time = timezone.now()
        query_time_ms = (end_time - start_time).total_seconds() * 1000
        ic("API execution time (ms):", query_time_ms)

        response_data = {
            'status': 'success',
            'description': f'Successfully retrieved {len(serializable_data_points)} data points.',
            'payload': {
                'sensor': {
                    'name': sensor.name,
                    'unit': sensor.effective_unit.symbol if sensor.effective_unit else '',
                    'data_type': sensor.effective_data_type,
                    'graph_type': sensor.graph_type,
                    'min_value': sensor.effective_min_value,
                    'max_value': sensor.effective_max_value
                },
                'query_range': {
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None
                },
                'query_time_ms': query_time_ms,
                'data_points': serializable_data_points
            }
        }
        
        return JsonResponse(response_data)

    except Exception as e:
        ic(f"Error fetching sensor readings: {e}")
        return JsonResponse({
            'status': 'error',
            'description': str(e),
            'payload': {}
        }, status=500)

@login_required
@log_execution_time
def lorawan_sensor_data_api(request, place_slug, pk):
    """
    API endpoint to get sensor readings from InfluxDB for a given LoRaWAN sensor.
    """
    try:
        user_timezone_str = request.GET.get('timezone')
        if user_timezone_str:
            timezone.activate(user_timezone_str)
        
        sensor = get_object_or_404(Sensor, pk=pk, device__location__place__slug=place_slug)
    except Sensor.DoesNotExist:
        return JsonResponse({"error": "Sensor not found"}, status=404)

    # Use the new helper to parse date range from GET parameters
    start_date, end_date, start_date_iso, end_date_iso, _ = _parse_date_range_from_params(request.GET)

    ic(start_date, end_date)

    try:
        from ..influx_graphs import get_influx_sensor_data
        data_points, query_time_ms = get_influx_sensor_data(sensor, start_date, end_date)

        # Manually convert Decimal to float for safe JSON serialization.
        # Also, convert datetime to ISO format string.
        serializable_data_points = []
        if data_points:
            for ts, val in data_points:
                # Ensure value is float for Chart.js, or None if it's null
                serializable_val = float(val) if val is not None else None
                serializable_data_points.append((ts.isoformat(), serializable_val))

        response_data = {
            'status': 'success',
            'description': f'Successfully retrieved {len(serializable_data_points)} data points.',
            'payload': {
                'sensor': {
                    'name': sensor.name,
                    'unit': sensor.effective_unit.symbol if sensor.effective_unit else '',
                    'data_type': sensor.effective_data_type,
                    'graph_type': sensor.graph_type,
                    'min_value': sensor.effective_min_value,
                    'max_value': sensor.effective_max_value,
                },
                'query_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                },
                'query_time_ms': query_time_ms,
                'data_points': serializable_data_points
            }
        }
        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'description': str(e),
            'payload': {}
        }, status=500)


@login_required
@log_execution_time
def sensor_readings_table_api(request: HttpRequest, place_slug: str, sensor_pk: int) -> JsonResponse:
    """
    API endpoint to get a rendered table of sensor readings for a given sensor.
    """
    try:
        sensor = get_object_or_404(
            Sensor,
            pk=sensor_pk,
            device__location__place__slug=place_slug
        )
        
        # Get start and end dates from query parameters
        start_str = request.GET.get('start')
        end_str = request.GET.get('end')
        
        queryset = SensorReading.objects.filter(sensor=sensor)

        if start_str and end_str:
            try:
                start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                queryset = queryset.filter(timestamp__gte=start_date, timestamp__lte=end_date)
            except ValueError:
                return JsonResponse({'error': 'Invalid date format.'}, status=400)
        else:
            # Default to the last 24 hours if no range is provided
            time_threshold = timezone.now() - timedelta(hours=24)
            queryset = queryset.filter(timestamp__gte=time_threshold)

        readings = queryset.order_by('-timestamp')
        
        # Render the template partial
        from django.template.loader import render_to_string
        html = render_to_string('sensors/includes/sensor_readings_table.html', {'readings': readings, 'sensor': sensor})
        
        return JsonResponse({'html': html})

    except Exception as e:
        # ic(f"Error fetching sensor readings table: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@login_required
def update_graph_type(request, place_slug, pk):
    """
    Update the graph type for a sensor.
    """
    try:
        data = json.loads(request.body)
        new_graph_type = data.get('graph_type')

        # Basic validation
        if new_graph_type not in ['LINE', 'SCATTER', 'BAR']:
            return JsonResponse({'success': False, 'error': 'Invalid graph type.'}, status=400)

        # Get the place and sensor
        place = get_object_or_404(Place, slug=place_slug)
        sensor = get_object_or_404(Sensor, pk=pk, device__location__place=place)

        # Update the sensor
        sensor.graph_type = new_graph_type
        sensor.save(update_fields=['graph_type'])

        return JsonResponse({'success': True, 'new_graph_type': new_graph_type})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def sensor_live_values_api(request: HttpRequest, place_slug: str) -> JsonResponse:
    """
    API endpoint to fetch the latest reading for multiple sensors at once.
    """
    pks_str = request.GET.get('pks', '')
    if not pks_str:
        return JsonResponse({'status': 'error', 'message': 'No sensor PKs provided.'}, status=400)

    pks = [int(pk) for pk in pks_str.split(',') if pk.isdigit()]
    
    # Ensure sensors belong to the place to prevent data leakage
    sensors = Sensor.objects.filter(pk__in=pks, device__location__place__slug=place_slug)
    
    payload = {}
    for sensor in sensors:
        try:
            update_sensor_live_value(sensor)
            # Re-fetch sensor to get the updated values
            sensor.refresh_from_db()

            if sensor.cached_reading_timestamp:
                payload[sensor.pk] = {
                    'status': 'success',
                    'value': sensor.cached_reading_value,
                    'timestamp': sensor.cached_reading_timestamp.isoformat(),
                    'unit_symbol': sensor.effective_unit.symbol,
                    'decimal_places': sensor.effective_decimal_places
                }
            else:
                payload[sensor.pk] = {'status': 'no_reading'}
        except Exception as e:
            payload[sensor.pk] = {'status': 'error', 'message': str(e)}

    # For any requested PKs that weren't found or didn't belong to the place
    found_pks = {s.pk for s in sensors}
    for pk in pks:
        if pk not in found_pks:
            payload[pk] = {'status': 'error', 'message': 'Sensor not found or access denied.'}

    return JsonResponse({'status': 'success', 'payload': payload})
