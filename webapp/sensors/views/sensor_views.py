from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.utils.decorators import method_decorator

from django.db.models import OuterRef, Subquery, Count, Q  # Count, Q, Exists
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.http import JsonResponse, HttpResponseRedirect

from django.utils import timezone
from django.utils.safestring import mark_safe

from ..models import Place, Device, Sensor, SensorReading
from .mixins import PlaceAnnotationMixin
from ..forms import SensorForm
from ..utils import get_sensor_readings

from datetime import datetime, timedelta
import sys
# import json
from icecream import ic

class SensorListView(LoginRequiredMixin, PlaceAnnotationMixin, ListView):
    model = Sensor
    context_object_name = 'sensors'
    template_name = 'sensors/sensor_list.html'

    def get_queryset(self) -> QuerySet[Sensor]:
        if not hasattr(self, '_queryset'):
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            
            # If we have a device_pk, filter by that device
            device_pk = self.kwargs.get('device_pk')
            if device_pk:
                device = get_object_or_404(Device, pk=device_pk, location__place=place)
                self._queryset = device.sensors.all()
            else:
                # Otherwise, get all sensors for the place
                self._queryset = Sensor.objects.filter(device__location__place=place)
            
            # Apply ordering and select related fields
            self._queryset = self._queryset.select_related(
                'device',
                'device__location',
                'device__location__place'
            ).order_by('-is_active', Lower('name'))
            
        return self._queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        context['place'] = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        
        # If we're looking at a specific device's sensors, add it to context
        device_pk = self.kwargs.get('device_pk')
        if device_pk:
            context['device'] = get_object_or_404(
                Device, 
                pk=device_pk,
                location__place=context['place']
            )
            context['location'] = context['device'].location
        
        # Add sensor statistics
        context.update({
            'sensors_active': self.get_queryset().filter(is_active=True).count(),
            'sensors_inactive': self.get_queryset().filter(is_active=False).count(),
        })
        
        return context

class SensorDetailView(LoginRequiredMixin, PlaceAnnotationMixin, DetailView):
    model = Sensor
    context_object_name = 'sensor'
    template_name = 'sensors/sensor_detail.html'
    object: Sensor

    def get_queryset(self) -> QuerySet[Sensor]:
        if not hasattr(self, '_queryset'):
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            base_queryset = super().get_queryset()
            
            # Filter sensors for this place and prefetch related fields
            self._queryset = base_queryset.filter(
                device__location__place=place
            ).select_related(
                'device',
                'device__location',
                'device__location__place'
            )
            
            # Get the last reading if it exists
            last_reading = SensorReading.objects.filter(
                sensor=OuterRef('pk')
            ).order_by('-timestamp')
            
            # Annotate with the last reading value and timestamp
            self._queryset = self._queryset.annotate(
                last_value=Subquery(
                    last_reading.values('value')[:1]
                ),
                last_reading_time=Subquery(
                    last_reading.values('timestamp')[:1]
                ))
        return self._queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        context['place'] = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        
        # Add device and location to context
        sensor = self.get_object()
        context['device'] = sensor.device
        context['location'] = sensor.device.location
        
        # Try to get recent readings if this is an InfluxDB sensor
        if sensor.data_type == 'INFLUX':
            try:
                # Get readings for the last hour
                stop = timezone.now()
                start = stop - timedelta(minutes=60)
                
                readings = get_sensor_readings(sensor=sensor, start=start, stop=stop, limit=100)
                if readings:
                    values = [reading['value'] for reading in readings]
                    context['readings_summary'] = {
                        'count': len(values),
                        'min': min(values),
                        'max': max(values),
                        'avg': sum(values) / len(values),
                        'first_timestamp': readings[0]['timestamp'],
                        'last_timestamp': readings[-1]['timestamp'],
                        'unit': sensor.unit
                    }
                    context['recent_readings'] = readings[:10]  # Last 10 readings
            except Exception as e:
                # ic(f"Error getting sensor readings: {str(e)}")
                context['readings_error'] = str(e)
        
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
        self._locations = self.get_annotated_locations(self._place)
        try:
            self._device = get_object_or_404(Device, pk=self.kwargs.get('device_pk', None))
        except Exception as e:
            # ic(f"Error getting device: {str(e)}")
            pass

        # Initialize inactive_help_text based on device status
        self._inactive_help_text = None
        
        # Only generate help text if we have a device, but don't create a dummy sensor
        if hasattr(self, '_device') and self._device:
            self._inactive_help_text = self.get_sensor_inactive_help_text(None, self._device)

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
                '<div class="form-text text-warning-emphasis mt-2">'
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                f'Sensor cannot be active because Device "{device.name}" is inactive.'
                '</div>'
            )
        # If sensor is active, create help text about deactivation
        elif sensor and sensor.is_active:
            inactive_help_text = mark_safe(
                '<div class="form-text text-warning-emphasis mt-2">'
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                'If deactivated, this sensor will no longer collect data and readings will not be available.'
                '</div>'
            )
        
        return inactive_help_text

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self._place
        kwargs['device'] = self._device
        kwargs['inactive_help_text'] = self._inactive_help_text
        
        # Set initial data properly
        kwargs['initial'] = kwargs.get('initial', {})
        
        # Set is_active based on device status
        if self._device:
            kwargs['initial']['is_active'] = self._device.is_active
        
        kwargs['initial'].update({
            'referrer': self.request.GET.get('next', '')
        })
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        context['place'] = self._place
        context['locations'] = self._locations
        context['device'] = self._device
        context['location'] = self._device.location
        
        # Add a fallback cancel URL
        context['cancel_fallback_url'] = reverse('sensors:device_detail', kwargs={
            'place_slug': self._place.slug,
            'pk': self._device.pk
        })
        return context

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
            f"Type: {sensor.get_sensor_type_display()}<br>"
            f"Unit: {sensor.unit}<br>"
            f"Status: {'Active' if sensor.is_active else 'inactive'}"
            f"</small>"
        )
        
        # Add inactive warning to message if sensor is inactive
        if not sensor.is_active and self._inactive_help_text:
            message += f"<br><small class='text-warning'>{self._inactive_help_text}</small>"
        
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
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class SensorUpdateView(LoginRequiredMixin, PlaceAnnotationMixin, UpdateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'
    object: Sensor

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place
        self._place = self.get_place()
        self._locations = self.get_annotated_locations(self._place)
        
        # Default inactive_help_text to None
        self._inactive_help_text = None
        self._device = None
        
        try:
            # Try to get the sensor if we're updating
            sensor = self.get_object()
            device = sensor.device
            self._device = device
            
            # Get help text based on sensor active state and its device
            self._inactive_help_text = self.get_sensor_inactive_help_text(sensor, device)
            
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
                '<div class="form-text text-warning-emphasis mt-2">'
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                f'This sensor will be inactive because Device "{device.name}" is inactive.'
                '</div>'
            )
        # If sensor is active, create help text about deactivation
        elif sensor and sensor.is_active:
            inactive_help_text = mark_safe(
                '<div class="form-text text-warning-emphasis mt-2">'
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                'If deactivated, this sensor will no longer collect data and readings will not be available.'
                '</div>'
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
        kwargs['inactive_help_text'] = self._inactive_help_text
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        context['place'] = self._place
        
        sensor = self.get_object()
        device = sensor.device
        context['device'] = device
        context['location'] = device.location
        context['locations'] = self._locations
        
        # Add a fallback cancel URL
        context['cancel_fallback_url'] = reverse('sensors:device_detail', kwargs={
            'place_slug': self._place.slug,
            'pk': device.pk
        })
        
        return context

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
            if self._original_values['name'] != form.cleaned_data['name']:
                changes.append(f"name: {self._original_values['name']} → {form.cleaned_data['name']}")
            if self._original_values['is_active'] != form.cleaned_data['is_active']:
                changes.append(f"active: {self._original_values['is_active']} → {form.cleaned_data['is_active']}")
            if self._original_values['device'] != form.cleaned_data['device']:
                changes.append(f"device: {self._original_values['device'].name} → {form.cleaned_data['device'].name}")
            if self._original_values['sensor_type'] != form.cleaned_data['sensor_type']:
                changes.append(f"type: {self._original_values['sensor_type']} → {form.cleaned_data['sensor_type']}")
            if self._original_values['data_type'] != form.cleaned_data['data_type']:
                changes.append(f"data source: {self._original_values['data_type']} → {form.cleaned_data['data_type']}")
            if self._original_values['unit'] != form.cleaned_data['unit']:
                changes.append(f"unit: {self._original_values['unit']} → {form.cleaned_data['unit']}")

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
            'place_slug': self.kwargs['place_slug'],
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
                    '<div class="form-text text-warning-emphasis mt-2">'
                    '<i class="bi bi-exclamation-triangle me-2"></i>'
                    f'This sensor is inactive because Device "{device.name}" is inactive.'
                    '</div>'
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
        context['place'] = self._place
        context['model_name'] = 'sensor'
        
        # Add sensor_url for cancel button
        context['sensor_url'] = reverse('sensors:sensor_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': sensor.pk
        })
        
        # Add a fallback cancel URL
        context['cancel_fallback_url'] = reverse('sensors:device_detail', kwargs={
            'place_slug': self._place.slug,
            'pk': device.pk
        })
        
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        sensor = self.object
        device = sensor.device
        location = device.location
        place = location.place
        
        # Store success_url before deletion
        success_url = self.get_success_url()
        
        message = (
            f"Deleted sensor <strong>{sensor.name}</strong> from "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name} > "
            f"<i class='bi bi-hdd-rack'></i> {device.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {sensor.get_sensor_type_display()}<br>"
            f"Unit: {sensor.unit}<br>"
            f"Status: {'Active' if sensor.is_active else 'inactive'}"
            f"</small>"
        )
        
        # Add inactive warning to message if sensor is inactive
        if not sensor.is_active and hasattr(self, '_inactive_help_text') and self._inactive_help_text:
            message += f"<br><small class='text-warning'>{self._inactive_help_text}</small>"
        
        # Delete the sensor
        sensor.delete()
        
        # Set toast message directly on request for middleware
        setattr(request, 'toast_message', {
            'message': message,
            'type': 'danger'
        })
        
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
        self._place = None
        self._sensor = None

    @property
    def place(self):
        """Cached place getter"""
        if self._place is None:
            place_slug = self.kwargs.get('place_slug')
            self._place = get_object_or_404(Place, slug=place_slug)
        return self._place

    @property
    def sensor(self):
        """Cached sensor getter"""
        if self._sensor is None:
            sensor_pk = self.kwargs.get('sensor_pk')
            if sensor_pk:
                self._sensor = get_object_or_404(
                    Sensor.objects.select_related(
                        'device',
                        'device__location'
                    ),
                    pk=sensor_pk,
                    device__location__place=self.place
                )
        return self._sensor

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Set initial timestamp to now
        kwargs['initial'] = {
            'timestamp': timezone.now()
        }
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'model_name': 'sensor_reading',
            'place': self.place,
            'sensor': self.sensor,
            'device': self.sensor.device,
            'location': self.sensor.device.location,
        })
        return context

    def form_valid(self, form):
        form.instance.sensor = self.sensor
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
            f"Value: {reading.value} {sensor.unit or '-'}<br>"
            f"Timestamp: {reading.timestamp}"
            f"</small>"
        )
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success'
        })
        
        # ic("SensorReadingCreateView setting toast_message:", {
        #     'message': message,
        #     'type': 'success'
        # })
        
        return response

    def get_success_url(self):
        return reverse('sensors:sensor_reading_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'sensor_pk': self.sensor.pk,
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
