from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.db.models import OuterRef, Subquery  # Count, Q, Exists
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.utils import timezone
from datetime import datetime

from ..models import Place, Device, Sensor, SensorReading
from ..forms import SensorForm
from ..utils import get_sensor_readings
from .mixins import PlaceAnnotationMixin

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
                readings = get_sensor_readings(sensor=sensor, minutes=60)
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

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self._place = self.get_place()
        self._locations = self.get_annotated_locations(self._place)
        self._device = get_object_or_404(Device, pk=self.kwargs.get('device_pk'), location__place=self._place)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self._place
        kwargs['locations'] = self._locations
        # this looks like it is first brining in any existing 'initial' values.
        kwargs['initial'] = kwargs.get('initial', {})
        # ic(self._device)
        kwargs['initial'].update({
            'device': self._device,
            'referrer': self.request.GET.get('next', '')
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # enrich the context with the place, locations, and device
        context['model_name'] = 'sensor'
        context['place'] = self._place
        context['locations'] = self._locations
        context['device'] = self._device
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        sensor = self.object
        device = sensor.device
        location = device.location
        place = location.place
        
        message = (
            f"Created sensor <strong>{sensor.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name} > "
            f"<i class='bi bi-hdd-rack'></i> {device.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {sensor.get_sensor_type_display()}<br>"
            f"Unit: {sensor.unit}<br>"
            f"Status: {'Active' if sensor.is_active else 'inactive'}"
            f"</small>"
        )
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        # ic("SensorCreateView setting toast_message:", {
        #     'message': message,
        #     'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        # })
        
        return response

    def get_success_url(self):
        return reverse('sensors:sensor_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class SensorUpdateView(LoginRequiredMixin, PlaceAnnotationMixin, UpdateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        context['place'] = self.get_place()
        
        sensor = self.get_object()
        context['device'] = sensor.device
        context['location'] = sensor.device.location
        
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
        
        response = super().form_valid(form)
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

        message = f"Updated location <strong>{sensor.name}</strong> in <i class='bi bi-house-gear'></i> {place.name}"
        if changes:
            message += f"<br><small class='text-muted'>{'; '.join(changes)}</small>"
        
        # Set toast message in request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if sensor.is_active else 'warning'
        })
        
        # ic("SensorUpdateView setting toast_message:", {
        #     'message': message,
        #     'type': 'success' if sensor.is_active else 'warning',
        #     'place_slug': self.kwargs.get('place_slug')
        # })
        
        return response

    def get_success_url(self):
        return reverse('sensors:sensor_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class SensorDeleteView(LoginRequiredMixin, PlaceAnnotationMixin, DeleteView):
    model = Sensor
    template_name = 'sensors/sensor_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sensor = self.get_object()
        
        # Add sensor_url for cancel button
        context['sensor_url'] = reverse('sensors:sensor_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': sensor.pk
        })
        
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        sensor = self.object
        device = sensor.device
        location = device.location
        place = location.place
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
        
        sensor.delete()
        
        # Set toast message directly on request for middleware
        setattr(request, 'toast_message', {
            'message': message,
            'type': 'danger'
        })
        
        ic("SensorDeleteView setting toast_message:", {
            'message': message,
            'type': 'danger'
        })
        
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        device = self.object.device
        return reverse('sensors:device_detail', kwargs={
            'place_slug': device.location.place.slug,
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
                messages.error(self.request, 'Invalid date format. Please use YYYY-MM-DD.')
        elif start_date or end_date:
            messages.error(self.request, 'Both start_date and end_date must be provided.')

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
        readings = get_sensor_readings(sensor=sensor, minutes=60)
        
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
