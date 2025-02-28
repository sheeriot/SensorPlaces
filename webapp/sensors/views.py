from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from .models import Place, Location, Device, Sensor, SensorReading
from .utils import get_sensor_readings  #, write_sensor_reading
from .forms import SensorForm, PlaceForm, DeviceForm
import folium
from django.conf import settings
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from typing import Any, Dict
from django.db.models.query import QuerySet
from django.db.models import Count, Q
import json
from django.views import View

from icecream import ic

# Place Views
class PlaceListView(ListView):
    model = Place
    context_object_name = 'places'
    template_name = 'sensors/place_list.html'

    def get_map_center(self, places):
        if not places.exists():
            # Default to Austin, TX if no places
            return 30.26715, -97.74306

        # Calculate average lat/lon
        total_lat = sum(float(place.latitude) for place in places)
        total_lon = sum(float(place.longitude) for place in places)
        count = places.count()
        
        return total_lat/count, total_lon/count

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        
        # Filter by place if slug provided
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            queryset = queryset.filter(slug=place_slug)

        # Annotate with counts for locations, devices, and sensors
        return queryset.annotate(
            locations_count=Count('locations', distinct=True),
            active_locations_count=Count(
                'locations',
                filter=Q(locations__is_active=True),
                distinct=True
            ),
            devices_count=Count(
                'locations__devices',
                distinct=True
            ),
            active_devices_count=Count(
                'locations__devices',
                filter=Q(locations__devices__is_active=True),
                distinct=True
            ),
            sensors_count=Count(
                'locations__devices__sensors',
                distinct=True
            ),
            active_sensors_count=Count(
                'locations__devices__sensors',
                filter=Q(locations__devices__sensors__is_active=True),
                distinct=True
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        places = self.get_queryset()
        # ic(places)
        
        # Get geographic center of all places
        center_lat, center_lon = self.get_map_center(places)
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=11)
        
        # Add markers for all places
        for place in places:
            # ic(vars(place))
            marker_color = 'green' if place.is_active else 'red'
            # Create rich tooltip with place details
            tooltip_html = f'''
                <div style="text-align: left">
                    <strong>{place.name}</strong><br>
                    <small>{place.address}</small><br>
                    <small>{place.latitude}, {place.longitude}</small><br>
                    <small>{place.locations.count()} locations</small>
                </div>
            '''
            
            place_popup = f'<a href="{reverse("sensors:place_detail", kwargs={"slug": place.slug})}">{place.name}</a>'
            folium.Marker(
                location=[float(place.latitude), float(place.longitude)],
                popup=place_popup,
                tooltip=folium.Tooltip(tooltip_html),
                icon=folium.Icon(color=marker_color, icon='info-sign'),
                options={'className': 'inactive-place' if not place.is_active else ''}
            ).add_to(m)
        
        # Add the map HTML to context
        context['map_html'] = m._repr_html_()
        return context

class PlaceDetailView(DetailView):
    model = Place
    context_object_name = 'place'
    template_name = 'sensors/place_detail.html'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        place = self.get_object()
        
        # Annotate devices and sensors
        devices = Device.objects.filter(location__place=place)
        sensors = Sensor.objects.filter(device__location__place=place)
        
        # Annotate locations with device counts
        locations = place.locations.annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        ).order_by('name')  # Add consistent ordering
        
        context['locations'] = locations
        
        # Create map centered on place
        m = folium.Map(
            location=[float(place.latitude), float(place.longitude)],
            zoom_start=15
        )
        
        # Add marker for the place
        folium.Marker(
            location=[float(place.latitude), float(place.longitude)],
            popup=place.name,
            tooltip=place.name,
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
        
        context['map_html'] = m._repr_html_()

        context.update({
            'devices_active': devices.filter(is_active=True).count(),
            'devices_inactive': devices.filter(is_active=False).count(),
            'sensors_active': sensors.filter(is_active=True).count(),
            'sensors_inactive': sensors.filter(is_active=False).count(),
        })
        return context

class PlaceCreateView(SuccessMessageMixin, CreateView):
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'
    success_url = reverse_lazy('sensors:place_list')
    success_message = "Place %(name)s was created successfully"

class PlaceUpdateView(SuccessMessageMixin, UpdateView):
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'
    success_url = reverse_lazy('sensors:place_list')
    success_message = "Place %(name)s was updated successfully"

class PlaceDeleteView(DeleteView):
    model = Place
    template_name = 'sensors/place_confirm_delete.html'
    success_url = reverse_lazy('sensors:place_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, f"Place {self.get_object().name} was deleted successfully") # type: ignore
        return super().delete(request, *args, **kwargs)

# Location Views
class LocationListView(ListView):
    model = Location
    context_object_name = 'locations'
    template_name = 'sensors/location_list.html'

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        
        # Filter by place if slug provided
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            queryset = queryset.filter(place__slug=place_slug)
        
        # Annotate with device counts
        return queryset.annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        ).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add place context if slug provided
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            place = get_object_or_404(Place, slug=place_slug)
            context['place'] = place
            
            # Create map centered on place
            if not place.site_plan:
                m = folium.Map(
                    location=[float(place.latitude), float(place.longitude)],
                    zoom_start=15
                )
                
                # Add marker for the place
                folium.Marker(
                    location=[float(place.latitude), float(place.longitude)],
                    popup=place.name,
                    tooltip=place.name,
                    icon=folium.Icon(color='red', icon='info-sign')
                ).add_to(m)
                
                # Add markers for all locations
                for location in self.get_queryset():
                    if location.x_coord and location.y_coord:
                        folium.Marker(
                            location=[float(location.x_coord), float(location.y_coord)],
                            popup=location.name,
                            tooltip=location.name + ' ' + (str(location.active_devices_count) if location.active_devices_count > 0 else ''),
                            icon=folium.Icon(color='blue', icon='info-sign')
                        ).add_to(m)
                
                context['map_html'] = m._repr_html_()
        ic(context)
        return context

class LocationDetailView(DetailView):
    model = Location
    template_name = 'sensors/location_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all locations for the place with device counts
        locations = self.object.place.locations.annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        ).order_by('name')  # Add consistent ordering

        # for location in locations:
        #     ic(location.name, location.active_devices_count, location.inactive_devices_count)

        # Add the annotated locations to the context
        context['place_locations'] = locations
        context['place'] = self.object.place
        
        # Get devices for this location with their sensor data
        devices = self.object.devices.all()
        device_data = []
        for device in devices:
            device_data.append({
                'device': device,
                'total_sensors': device.sensors.count(),
                'active_sensors': device.sensors.filter(is_active=True).count(),
            })
        
        context['device_data'] = device_data
        context['total_devices'] = devices.count()
        context['active_devices'] = devices.filter(is_active=True).count()
        
        return context

class LocationCreateView(SuccessMessageMixin, CreateView):
    model = Location
    fields = ['name', 'is_active']
    template_name = 'sensors/location_form.html'
    success_message = "Location %(name)s was created successfully"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
        return context

    def form_valid(self, form):
        place = get_object_or_404(Place, slug=self.kwargs.get('place_slug'))
        form.instance.place = place
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('sensors:place_locations', kwargs={'place_slug': self.object.place.slug})

class LocationUpdateView(SuccessMessageMixin, UpdateView):
    model = Location
    fields = ['name', 'is_active']
    template_name = 'sensors/location_form.html'
    success_message = "Location %(name)s was updated successfully"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
        return context

    def get_success_url(self):
        return reverse('sensors:place_locations', kwargs={'place_slug': self.object.place.slug})

class LocationDeleteView(DeleteView):
    model = Location
    template_name = 'sensors/location_confirm_delete.html'

    def get_success_url(self):
        return reverse('sensors:place_locations', kwargs={'place_slug': self.object.place.slug})

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, f"Location {self.get_object().name} was deleted successfully")
        return super().delete(request, *args, **kwargs)

# Device Views
class DeviceListView(ListView):
    model = Device
    context_object_name = 'devices'
    template_name = 'sensors/device_list.html'

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        place_slug = self.kwargs.get('place_slug')
        location_pk = self.kwargs.get('location_pk')
        
        if place_slug:
            queryset = queryset.filter(location__place__slug=place_slug)
            if location_pk:
                queryset = queryset.filter(location_id=location_pk)
        
        return queryset

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        place_slug = self.kwargs.get('place_slug')
        location_pk = self.kwargs.get('location_pk')
        
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
            # Get all locations for this place with device counts
            locations = context['place'].locations.annotate(
                active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
                inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
            )
            context['place_locations'] = locations
            if location_pk:
                # Get current location with annotations
                context['location'] = locations.get(pk=location_pk)
            
            # Add total active devices count
            context['active_devices_count'] = Device.objects.filter(
                location__place=context['place'],
                is_active=True
            ).count()
        
        return context

class DeviceDetailView(DetailView):
    model = Device
    context_object_name = 'device'
    template_name = 'sensors/device_detail.html'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        sensors = self.object.sensors.all()
        
        context.update({
            'total_sensors': sensors.count(),
            'active_sensors': sensors.filter(is_active=True).count(),
            'sensors': sensors,  # Pass all sensors to template
        })
        return context

class DeviceCreateView(SuccessMessageMixin, CreateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'
    success_message = "Device %(name)s was created successfully"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        place_slug = self.kwargs.get('place_slug')
        location_pk = self.kwargs.get('location_pk')
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
            if location_pk:
                # Get all locations for this place with device counts
                locations = context['place'].locations.annotate(
                    active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
                    inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
                )
                context['place_locations'] = locations
                # Get current location with annotations
                context['location'] = locations.get(pk=location_pk)
        return context

    def get_initial(self):
        initial = super().get_initial()
        location = get_object_or_404(Location, pk=self.kwargs.get('location_pk'))
        initial['place_slug'] = self.kwargs.get('place_slug')
        initial['location_pk'] = self.kwargs.get('location_pk')
        if not location.is_active:
            initial['is_active'] = False
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        location = get_object_or_404(Location, pk=self.kwargs.get('location_pk'))
        if not location.is_active:
            form.fields['is_active'].disabled = True
        return form

    def form_valid(self, form):
        location_pk = self.kwargs.get('location_pk')
        location = get_object_or_404(Location, pk=location_pk)
        form.instance.location = location
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.object.location.place.slug,
            'location_pk': self.object.location.pk,
            'pk': self.object.pk
        })

class DeviceUpdateView(SuccessMessageMixin, UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'
    success_message = "Device %(name)s was updated successfully"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        place_slug = self.kwargs.get('place_slug')
        location_pk = self.kwargs.get('location_pk')
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
            if location_pk:
                # Get all locations for this place with device counts
                locations = context['place'].locations.annotate(
                    active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
                    inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
                )
                context['place_locations'] = locations
                # Get current location with annotations
                context['location'] = locations.get(pk=location_pk)
        return context

    def get_initial(self):
        initial = super().get_initial()
        initial['place_slug'] = self.kwargs.get('place_slug')
        initial['location_pk'] = self.kwargs.get('location_pk')
        return initial

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.object.location.place.slug,
            'location_pk': self.object.location.pk,
            'pk': self.object.pk
        })

    def form_valid(self, form):
        response = super().form_valid(form)
        # If device is set to inactive, cascade to all sensors
        if not form.instance.is_active:
            self.object.sensors.all().update(is_active=False)
        return response

class DeviceDeleteView(DeleteView):
    model = Device
    template_name = 'sensors/device_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        place_slug = self.kwargs.get('place_slug')
        location_pk = self.kwargs.get('location_pk')
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
            if location_pk:
                context['location'] = get_object_or_404(Location, pk=location_pk, place=context['place'])
        return context

    def get_success_url(self):
        return reverse('sensors:location_detail',
                      kwargs={'place_slug': self.object.location.place.slug,
                             'pk': self.object.location.pk})

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, f"Device {self.get_object().name} was deleted successfully")
        return super().delete(request, *args, **kwargs)

# Sensor Views
class SensorListView(ListView):
    model = Sensor
    context_object_name = 'sensors'
    template_name = 'sensors/sensor_list.html'

    def get_queryset(self):
        queryset = super().get_queryset()
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            queryset = queryset.filter(device__location__place__slug=place_slug)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
        return context

class SensorDetailView(DetailView):
    model = Sensor
    context_object_name = 'sensor'
    template_name = 'sensors/sensor_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get recent readings from InfluxDB
        context['influx_readings'] = get_sensor_readings(
            sensor=self.object,
            limit=100
        )
        return context

class SensorCreateView(SuccessMessageMixin, CreateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'
    success_message = "Sensor %(name)s was created successfully"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        device_pk = self.kwargs.get('device_pk')
        context['device'] = get_object_or_404(Device, pk=device_pk)
        return context

    def get_initial(self):
        initial = super().get_initial()
        device = get_object_or_404(Device, pk=self.kwargs.get('device_pk'))
        # Set initial active state based on device state
        if not device.is_active:
            initial['is_active'] = False
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        device = get_object_or_404(Device, pk=self.kwargs.get('device_pk'))
        if not device.is_active:
            form.fields['is_active'].disabled = True
            form.fields['is_active'].initial = False
        return form

    def form_valid(self, form):
        device_pk = self.kwargs.get('device_pk')
        device = get_object_or_404(Device, pk=device_pk)
        form.instance.device = device
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.object.device.location.place.slug,
            'location_pk': self.object.device.location.pk,
            'pk': self.object.device.pk
        })

class SensorUpdateView(SuccessMessageMixin, UpdateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'
    success_message = "Sensor %(name)s was updated successfully"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['device'] = self.object.device
        return context

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.object.device.location.place.slug,
            'location_pk': self.object.device.location.pk,
            'pk': self.object.device.pk
        })

class SensorDeleteView(DeleteView):
    model = Sensor
    template_name = 'sensors/sensor_confirm_delete.html'
    
    def get_success_url(self):
        # Get the place_slug and location_pk from the sensor's device
        place_slug = self.object.device.location.place.slug
        location_pk = self.object.device.location.pk
        return reverse('sensors:device_detail', kwargs={
            'place_slug': place_slug,
            'location_pk': location_pk,
            'pk': self.object.device.pk
        })

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, f"Sensor {self.get_object().name} was deleted successfully")
        return super().delete(request, *args, **kwargs)

# SensorReading Views
class SensorReadingListView(ListView):
    model = SensorReading
    context_object_name = 'readings'
    template_name = 'sensors/reading_list.html'
    ordering = ['-timestamp']
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            queryset = queryset.filter(sensor__device__location__place__slug=place_slug)
        return queryset.order_by(self.ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
        return context

class SensorReadingDetailView(DetailView):
    model = SensorReading
    context_object_name = 'reading'
    template_name = 'sensors/reading_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add InfluxDB detailed data for this reading
        return context

class SensorReadingCreateView(SuccessMessageMixin, CreateView):
    model = SensorReading
    fields = ['sensor', 'value', 'notes']
    template_name = 'sensors/reading_form.html'
    success_message = "Reading for %(sensor)s was created successfully"

    def get_success_url(self):
        return reverse('sensors:place_readings', kwargs={'place_slug': self.object.sensor.device.location.place.slug})

    def form_valid(self, form):
        response = super().form_valid(form)
        # Write to InfluxDB
        success = write_sensor_reading(
            sensor=form.instance.sensor,
            value=form.instance.value,
            timestamp=form.instance.timestamp
        )
        if not success:
            messages.warning(self.request, "Reading saved to database but failed to write to InfluxDB")
        return response

def place_stats(request: HttpRequest, place_slug: str) -> JsonResponse:
    place = get_object_or_404(Place, slug=place_slug)
    
    # Get device and sensor counts
    devices_active = Device.objects.filter(location__place=place, is_active=True)
    devices_inactive = Device.objects.filter(location__place=place, is_active=False)
    sensors_active = Sensor.objects.filter(device__location__place=place, is_active=True)
    sensors_inactive = Sensor.objects.filter(device__location__place=place, is_active=False)
    
    # Get location statistics
    locations = place.locations.annotate(
        active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
        inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
    ).values('id', 'name', 'is_active', 'active_devices_count', 'inactive_devices_count')
    
    return JsonResponse({
        'devices_active': devices_active.count(),
        'devices_inactive': devices_inactive.count(),
        'sensors_active': sensors_active.count(),
        'sensors_inactive': sensors_inactive.count(),
        'locations': list(locations)
    })

# @staff_member_required
@require_POST
def location_update_position(request: HttpRequest, place_slug: str, pk: int) -> JsonResponse:
    location = get_object_or_404(Location, pk=pk)
    if place_slug != location.place.slug:
        return JsonResponse({'status': 'error', 'message': 'Invalid place slug'}, status=400)
    try:
        data = json.loads(request.body)
        location.x_coord = data.get('x_coord')
        location.y_coord = data.get('y_coord')
        location.save()
        return JsonResponse({'status': 'success'})
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
def sensor_toggle_active(request, place_slug, pk):
    """Toggle sensor active status"""
    sensor = get_object_or_404(Sensor, pk=pk,
                              device__location__place__slug=place_slug)
    
    # Toggle the status
    sensor.is_active = not sensor.is_active
    sensor.save()
    
    # Get updated statistics
    device = sensor.device
    total_sensors = device.sensors.count()
    active_sensors = device.sensors.filter(is_active=True).count()
    
    return JsonResponse({
        'status': 'success',
        'is_active': sensor.is_active,
        'total_sensors': total_sensors,
        'active_sensors': active_sensors,
    })

class DeviceToggleActiveView(View):
    def post(self, request, place_slug, pk):
        device = get_object_or_404(Device, pk=pk)
        
        try:
            data = json.loads(request.body)
            is_active = data.get('is_active', False)
            
            # Update device status
            device.is_active = is_active
            device.save()
            
            # If device is set to inactive, cascade to all sensors
            if not is_active:
                device.sensors.all().update(is_active=False)
            
            # Get updated statistics for the location
            location = device.location
            active_devices_count = location.devices.filter(is_active=True).count()
            inactive_devices_count = location.devices.filter(is_active=False).count()
            
            # Get total active devices count for the place
            total_active_devices = Device.objects.filter(
                location__place=location.place,
                is_active=True
            ).count()
            
            return JsonResponse({
                'status': 'success',
                'is_active': device.is_active,
                'active_devices_count': active_devices_count,
                'inactive_devices_count': inactive_devices_count,
                'total_active_devices': total_active_devices,
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class DeviceMoveLocationView(View):
    def post(self, request, pk):
        # Get the device and validate it exists
        device = get_object_or_404(Device, pk=pk)
        ic('device move location - from', device.location)
        
        try:
            data = json.loads(request.body)
            new_location_id = data.get('new_location_id')
            # ic('new_location_id', new_location_id)
            if not new_location_id:
                return JsonResponse({'error': 'new_location_id is required'}, status=400)
            
            # Get the new location and validate it exists
            new_location = get_object_or_404(Location, pk=new_location_id)
            # ic('new_location', new_location)
            # Store old location for counter updates
            old_location = device.location
            
            # Validate that the new location is active
            if not new_location.is_active:
                return JsonResponse(
                    {'error': 'Cannot move device to inactive location'}, 
                    status=400
                )
            
            # Validate that the new location belongs to the same place
            if new_location.place != device.location.place:
                return JsonResponse(
                    {'error': 'Cannot move device to a different place'}, 
                    status=400
                )
            
            # Update the device's location
            device.location = new_location
            device.save()
            # ic('saved device.location', device.location)
            # Get updated counts
            old_location_count = old_location.devices.filter(is_active=True).count()
            new_location_count = new_location.devices.filter(is_active=True).count()
            results = JsonResponse({
                'success': True,
                'new_location_name': new_location.name,
                'old_location_count': old_location_count,
                'new_location_count': new_location_count,
                'total_active_devices': Device.objects.filter(
                    location__place=device.location.place,
                    is_active=True
                ).count()
            })
            ic('results', results)
            return results
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

@require_POST
def update_site_plan_layout(request, slug):
    """Update the site plan layout settings for a place"""
    if not request.user.has_perm('sensors.change_place'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
        
    place = get_object_or_404(Place, slug=slug)
    try:
        data = json.loads(request.body)
        place.site_plan_scale = float(data.get('site_plan_scale', 1.0))
        place.site_plan_x = float(data.get('site_plan_x', 0))
        place.site_plan_y = float(data.get('site_plan_y', 0))
        place.save(update_fields=['site_plan_scale', 'site_plan_x', 'site_plan_y'])
        return JsonResponse({'status': 'success'})
    except (ValueError, json.JSONDecodeError) as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Server error'}, status=500)

@require_POST
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
