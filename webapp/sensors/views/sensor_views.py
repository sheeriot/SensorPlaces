from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.utils.decorators import method_decorator

from django.db.models import OuterRef, Subquery, Count, Min, Max, Prefetch, Q
from django.db.models.functions import Lower

from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.http import JsonResponse, HttpResponseRedirect, HttpRequest

from django.utils import timezone
from django.utils.safestring import mark_safe

from ..models import Device, Sensor, SensorReading, Place, Location
from .mixins import PlaceAnnotationMixin
from .sensor_forms import SensorForm, LoRaWANSensorForm
from ..utils import get_sensor_readings, generate_sparkline
from .views_fun import get_annotated_locations, get_live_counts_context
from ..decorators import log_execution_time

from datetime import datetime, timedelta, timezone as dt_timezone

from icecream import ic
from django.template.loader import render_to_string

from django.views.decorators.http import require_POST
import json

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

def parse_date(date_str, is_end_date=False):
    """Parses a date string from various formats and returns a timezone-aware datetime object."""
    # Try parsing ISO 8601 format first (e.g., '2025-07-01T04:00:00+00:00')
    try:
        # fromisoformat handles timezone info automatically
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        pass  # If it fails, try the other formats

    # Try parsing custom formats
    try:
        if len(date_str) == 8:
            dt = datetime.strptime(date_str, '%Y%m%d')
        else:
            dt = datetime.strptime(date_str, '%Y%m%d%H%M')
        
        # Make the datetime timezone-aware in UTC
        aware_dt = dt.replace(tzinfo=dt_timezone.utc)
    
        # If it's an end date with no time specified, set it to the end of the day
        if is_end_date and len(date_str) == 8:
            aware_dt += timedelta(days=1, microseconds=-1)
    
        return aware_dt
    except (ValueError, TypeError):
        # If all parsing fails, raise an error or handle it as needed
        raise ValueError(f"Unable to parse date string: {date_str}")


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
        start_date = parse_date(start_date_str)
        end_date = parse_date(end_date_str, is_end_date=True)
        start_date_iso = start_date.isoformat()
        # For display, use the date part of the original string to avoid off-by-one day
        end_date_iso = parse_date(end_date_str, is_end_date=False).isoformat()
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
        
        # Add device and location to context
        sensor = self.get_object()

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
        graph_readings_qs = SensorReading.objects.filter(sensor=sensor)
        if start_date and end_date:
            graph_readings_qs = graph_readings_qs.filter(timestamp__gte=start_date, timestamp__lte=end_date)
        
        context['readings'] = graph_readings_qs.order_by('timestamp')

        # Overall statistics are NOT filtered by the date range.
        all_readings_qs = SensorReading.objects.filter(sensor=sensor)

        if sensor.device.is_lorawan:
            # For LoRaWAN, stats come from InfluxDB and should reflect the full history.
            from ..influx_graphs import get_lorawan_sensor_stats
            stats_data = get_lorawan_sensor_stats(sensor)
            # ic(stats_data)
            if stats_data:
                stats = {
                    'reading_count': stats_data.get('reading_count'),
                    'first_reading': stats_data.get('first_reading'),
                    'last_reading': stats_data.get('last_reading')
                }
            else:
                stats = {
                    'reading_count': 'N/A',
                    'first_reading': 'N/A',
                    'last_reading': 'N/A'
                }
        else:
            # For direct readings, aggregate over the entire unfiltered set.
            stats = all_readings_qs.aggregate(
                first_reading=Min('timestamp'),
                last_reading=Max('timestamp'),
                reading_count=Count('id')
            )
        context['reading_stats'] = stats

        # Generate sparkline based on the filtered graph data
        if not sensor.device.is_lorawan:
            timestamps = [reading.timestamp for reading in context['readings']]
            context['sparkline_image'] = generate_sparkline(timestamps)
        
        # Add locations for the place_nav_card
        context['locations'] = get_annotated_locations(self._place)
        
        return context

class SensorCreateView(LoginRequiredMixin, PlaceAnnotationMixin, CreateView):
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
        
        # Set initial data properly
        kwargs['initial'] = kwargs.get('initial', {})
        
        # Set is_active based on device status
        if self._device:
            kwargs['initial']['is_active'] = self._device.is_active
        
        kwargs['initial'].update({
            'referrer': self.request.GET.get('next', '')
        })
        
        kwargs['cancel_url'] = self.get_cancel_url()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        # Place is already in context from PlaceAnnotationMixin
        
        # Add device and location data
        if hasattr(self, '_device') and self._device:
            context['device'] = self._device
            context['location'] = self._device.location
        
        # Add a fallback cancel URL
        context['cancel_url'] = self.get_cancel_url()
        return context

    def get_cancel_url(self):
        cancel_url = self.request.META.get('HTTP_REFERER')
        if not cancel_url:
            if hasattr(self, '_device') and self._device:
                cancel_url = reverse('sensors:device_detail', kwargs={
                    'place_slug': self._place.slug,
                    'pk': self._device.pk
                })
            else:
                # Fallback to place detail if no device specified
                cancel_url = reverse('sensors:place_detail', kwargs={
                    'place_slug': self._place.slug
                })
        return cancel_url

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

    def get_success_url(self):
        return reverse('sensors:sensor_detail', kwargs={
            'place_slug': self._place.slug,
            'pk': self.object.pk
        })

class LoRaWANSensorCreateView(LoginRequiredMixin, PlaceAnnotationMixin, CreateView):
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
        kwargs['cancel_url'] = reverse('sensors:device_detail', kwargs={'place_slug': self.place.slug, 'pk': self.device.pk})
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

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={'place_slug': self.place.slug, 'pk': self.device.pk})


class SensorUpdateView(LoginRequiredMixin, PlaceAnnotationMixin, UpdateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'
    object: Sensor

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

    def get_initial(self):
        initial = super().get_initial()
        # Set the referrer in initial data
        initial['referrer'] = self.request.META.get('HTTP_REFERER', '')
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self._place
        kwargs['device'] = self._device
        kwargs['cancel_url'] = self.get_cancel_url()
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        # Place is already in context from PlaceAnnotationMixin
        
        sensor = self.get_object()
        device_pk = sensor.device.pk
        device_qs = Device.objects.annotate(
            active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)),
            inactive_sensors_count=Count('sensors', filter=Q(sensors__is_active=False))
        )
        device = get_object_or_404(device_qs, pk=device_pk)
        context['device'] = device
        context['location'] = device.location
        
        # Add a fallback cancel URL
        context['cancel_url'] = self.get_cancel_url()
        return context

    def get_cancel_url(self):
        cancel_url = self.request.META.get('HTTP_REFERER')
        if not cancel_url:
            cancel_url = reverse('sensors:device_detail', kwargs={
                'place_slug': self._place.slug,
                'pk': self.object.device.pk
            })
        return cancel_url

    def form_valid(self, form):

        
        # Store original values before save
        sensor = self.get_object()
        self._original_values = {
            'name': sensor.name,
            'is_active': sensor.is_active,
            'device': sensor.device,
            'sensor_type': sensor.sensor_type,
            'data_type': sensor.data_type,
            'unit': sensor.unit
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
            if 'unit' in self._original_values and self._original_values['unit'] != sensor.effective_unit:
                # Need to import Unit at the top
                from ..models import Unit
                original_unit_pk = self._original_values['unit']
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

    def get_success_url(self):
        # Use cleaned_data from the form instead of request.POST
        if hasattr(self, 'object') and hasattr(self.object, 'referrer') and self.object.referrer:
            return self.object.referrer
        # Or check form's cleaned_data
        elif hasattr(self, 'form') and 'referrer' in self.form.cleaned_data and self.form.cleaned_data['referrer']:
            return self.form.cleaned_data['referrer']
        # Fallback to default URL
        return reverse('sensors:sensor_detail', kwargs={
            'place_slug': self._place.slug,
            'pk': self.object.pk
        })

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
        self.object = self.get_object()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            context = self.get_context_data(object=self.object)
            html = render_to_string('sensors/sensor_confirm_delete_modal.html', context, request=request)
            return JsonResponse({'html': html})
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        sensor = self.object
        device = sensor.device
        location = device.location
        place = location.place
        
        # Before deleting the sensor, store its data
        sensor_data = {
            'name': sensor.name,
            'is_active': sensor.is_active,
            'sensor_type': sensor.sensor_type or '',
            'data_type': sensor.get_effective_data_type_display,
            'unit': sensor.effective_unit or ''
        }
        
        message = (
            f"Deleted sensor <strong>{sensor_data['name']}</strong> from "
            f"<i class='bi bi-hdd-rack'></i> {device.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {sensor_data['sensor_type']}<br>"
            f"Data type: {sensor_data['data_type']}<br>"
            f"Unit: {sensor_data['unit']}<br>"
            f"Status: {'Active' if sensor_data['is_active'] else 'inactive'}"
        )
        
        message += "</small>"
        
        # Create toast message
        request.toast_message = {
            'message': message,
            'type': 'warning'
        }
        
        # Delete the sensor
        sensor.delete()
        
        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'redirect_url': success_url})
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
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
        
        readings = get_sensor_readings(sensor=sensor, start=start, stop=stop, limit=100)
        
        if not readings:
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
    """
    try:
        sensor = get_object_or_404(
            Sensor,
            pk=pk,
            device__location__place__slug=place_slug
        )
        
        # Use the new helper to parse date range from GET parameters
        start_date, end_date, start_date_iso, end_date_iso, _ = _parse_date_range_from_params(request.GET)

        queryset = SensorReading.objects.filter(sensor=sensor)

        if start_date and end_date:
            queryset = queryset.filter(timestamp__gte=start_date, timestamp__lte=end_date)
        else:
            # Default to the last 24 hours if no range is provided
            time_threshold = timezone.now() - timedelta(hours=24)
            queryset = queryset.filter(timestamp__gte=time_threshold)

        readings = queryset.order_by('timestamp').values('timestamp', 'value')
        
        # Format data into the new structure
        data_points = [{'x': r['timestamp'].isoformat(), 'y': r['value']} for r in readings]

        response_data = {
            'sensor': {
                'name': sensor.name,
                'unit': sensor.effective_unit.symbol if sensor.effective_unit else '',
                'data_type': sensor.effective_data_type,
                'graph_type': sensor.graph_type,
                'min_value': sensor.effective_min_value,
                'max_value': sensor.effective_max_value
            },
            'query_range': {
                'start_date': start_date_iso if start_date else None,
                'end_date': end_date_iso if end_date else None
            },
            'data_points': data_points
        }
        
        return JsonResponse(response_data)

    except Exception as e:
        # ic(f"Error fetching sensor readings: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@log_execution_time
def lorawan_sensor_data_api(request, place_slug, pk):
    """
    API endpoint to get sensor readings from InfluxDB for a given LoRaWAN sensor.
    """
    try:
        sensor = get_object_or_404(Sensor, pk=pk, device__location__place__slug=place_slug)
    except Sensor.DoesNotExist:
        return JsonResponse({"error": "Sensor not found"}, status=404)

    # Use the new helper to parse date range from GET parameters
    start_date, end_date, start_date_iso, end_date_iso, _ = _parse_date_range_from_params(request.GET)

    try:
        from ..influx_graphs import get_lorawan_sensor_data
        data_points = get_lorawan_sensor_data(sensor, start_date, end_date)

        # Manually convert Decimal to float for safe JSON serialization.
        # Also, convert datetime to ISO format string.
        serializable_data_points = []
        if data_points:
            for ts, val in data_points:
                # Ensure value is float for Chart.js, or None if it's null
                serializable_val = float(val) if val is not None else None
                serializable_data_points.append((ts.isoformat(), serializable_val))

        response_data = {
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
            'data_points': serializable_data_points,
        }
        return JsonResponse(response_data)

    except Exception as e:
        # ic(f"Error fetching LoRaWAN sensor data: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
