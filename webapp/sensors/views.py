from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from .models import Place, Location, Device, Sensor, SensorReading
from .utils import get_sensor_readings  #, write_sensor_reading
from .forms import SensorForm, PlaceForm, DeviceForm, LocationForm
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
from django.contrib.auth.mixins import LoginRequiredMixin
import time
from django.utils import timezone

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
        context['model_name'] = 'place'
        places = self.get_queryset()
        # places)
        
        # Get geographic center of all places
        center_lat, center_lon = self.get_map_center(places)
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=11)
        
        # Add markers for all places
        for place in places:
            # vars(place))
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
            
            place_popup = f'<a href="{reverse("sensors:place_detail", kwargs={"place_slug": place.slug})}">{place.name}</a>'
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
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
        context['active_tab'] = 'locations'  # Default active tab
        place = self.get_object()
        
        # Annotate locations with device counts
        locations = place.locations.annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        ).order_by('name')
        
        context['locations'] = locations
        
        # Create map centered on place
        if place.latitude and place.longitude:
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
            context['show_map'] = True

        context.update({
            'devices_active': Device.objects.filter(location__place=place, is_active=True).count(),
            'devices_inactive': Device.objects.filter(location__place=place, is_active=False).count(),
            'sensors_active': Sensor.objects.filter(device__location__place=place, is_active=True).count(),
            'sensors_inactive': Sensor.objects.filter(device__location__place=place, is_active=False).count(),
        })
        return context

class PlaceCreateView(SuccessMessageMixin, CreateView):
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'
    success_message = "Place %(name)s was created successfully"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Add referrer to form kwargs
        referrer = self.request.META.get('HTTP_REFERER')
        if referrer:
            kwargs['referrer'] = referrer
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
        return context

    def get_success_url(self):
        # Try to get the referrer from the form data
        referrer = self.request.POST.get('referrer')
        if referrer:
            return referrer
            
        # Fall back to the default URL if no referrer
        return reverse('sensors:place_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': self.get_success_message(form.cleaned_data),
                'redirect_url': self.get_success_url()
            })
        return response

class PlaceUpdateView(SuccessMessageMixin, UpdateView):
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'
    success_message = "Place %(name)s was updated successfully"
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Add referrer to form kwargs
        referrer = self.request.META.get('HTTP_REFERER')
        if referrer:
            kwargs['referrer'] = referrer
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
        return context

    def get_success_url(self):
        # Try to get the referrer from the form data
        referrer = self.request.POST.get('referrer')
        if referrer:
            return referrer
            
        # Fall back to the default URL if no referrer
        return reverse('sensors:place_detail', kwargs={'place_slug': self.object.slug})

    def form_valid(self, form):
        response = super().form_valid(form)
        if not form.instance.is_active:
            self.object.locations.all().update(is_active=False)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': self.get_success_message(form.cleaned_data),
                'redirect_url': self.get_success_url()
            })
        return response

class PlaceDeleteView(DeleteView):
    model = Place
    template_name = 'sensors/place_confirm_delete.html'
    success_url = reverse_lazy('sensors:place_list')
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'
    
    def delete(self, request, *args, **kwargs):
        place = self.get_object()
        response = super().delete(request, *args, **kwargs)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': f"Place {place.name} was deleted successfully",
                'redirect_url': str(self.success_url)
            })
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
        return context

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
        # Annotate with device active counts
        return queryset.annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        place_slug = self.kwargs.get('place_slug')

        if place_slug:
            locations = Location.objects.filter(
                place__slug=place_slug
            ).annotate(
                active_devices_count=Count(
                    'devices',
                    filter=Q(devices__is_active=True)
                ),
                inactive_devices_count=Count(
                    'devices',
                    filter=Q(devices__is_active=False)
                )
            ).order_by('name')

            context['locations'] = locations
            
            if self.kwargs.get('location_pk'):
                context['location'] = locations.filter(pk=self.kwargs.get('location_pk')).first()

        return context

class LocationDetailView(DetailView):
    model = Location
    context_object_name = 'location'
    template_name = 'sensors/location_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        location = self.get_object()
        context['location'] = location
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
            # context['place_url'] = reverse('sensors:place_detail', kwargs={'place_slug': place_slug})
            context['locations'] = context['place'].locations.annotate(
                active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
                inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
            )
            context['devices'] = location.devices.all()
        return context

class LocationCreateView(SuccessMessageMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'
    success_message = "Location %(name)s was created successfully"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Add referrer to form kwargs
        referrer = self.request.META.get('HTTP_REFERER')
        if referrer:
            kwargs['referrer'] = referrer
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
            context['place_url'] = reverse('sensors:place_detail', kwargs={'place_slug': place_slug})
            context['locations'] = context['place'].locations.annotate(
                active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
                inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
            )
        return context

    def form_valid(self, form):
        place = get_object_or_404(Place, slug=self.kwargs.get('place_slug'))
        form.instance.place = place
        response = super().form_valid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': self.get_success_message(form.cleaned_data),
                'redirect_url': self.get_success_url()
            })
        return response

    def get_success_url(self):
        # Try to get the referrer from the form data
        referrer = self.request.POST.get('referrer')
        if referrer:
            return referrer
            
        # Fall back to the default URL if no referrer
        return reverse('sensors:place_locations', kwargs={'place_slug': self.object.place.slug})

class LocationUpdateView(SuccessMessageMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'
    success_message = "Location %(name)s was updated successfully"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Add referrer to form kwargs
        referrer = self.request.META.get('HTTP_REFERER')
        if referrer:
            kwargs['referrer'] = referrer
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            context['place'] = get_object_or_404(Place, slug=place_slug)
            context['place_url'] = reverse('sensors:place_detail', kwargs={'place_slug': place_slug})
            context['locations'] = context['place'].locations.annotate(
                active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
                inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
            )
        return context

    def get_success_url(self):
        # Try to get the referrer from the form data
        referrer = self.request.POST.get('referrer')
        if referrer:
            return referrer
            
        # Fall back to the default URL if no referrer
        return reverse('sensors:place_locations', kwargs={'place_slug': self.object.place.slug})

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': self.get_success_message(form.cleaned_data),
                'redirect_url': self.get_success_url()
            })
        return response

class LocationDeleteView(DeleteView):
    model = Location
    template_name = 'sensors/location_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        place_slug = self.kwargs.get('place_slug')
        context['place'] = get_object_or_404(Place, slug=place_slug)
        context['locations'] = context['place'].locations.annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        )
        location = get_object_or_404(Location, pk=self.kwargs.get('pk'))
        context['location'] = location
        context['place_url'] = reverse('sensors:place_locations', kwargs={
            'place_slug': self.object.place.slug
        })
        return context

    def get_success_url(self):
        return reverse('sensors:place_locations', kwargs={'place_slug': self.object.place.slug})

    def delete(self, request, *args, **kwargs):
        location = self.get_object()
        success_url = self.get_success_url()
        response = super().delete(request, *args, **kwargs)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': f"Location {location.name} was deleted successfully",
                'redirect_url': success_url
            })
        return response

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
        
        return queryset.select_related(
            'location', 
            'location__place'
        ).prefetch_related(
            'sensors'
        ).annotate(
            active_sensors=Count('sensors', filter=Q(sensors__is_active=True)),
            total_sensors=Count('sensors')
        ).order_by(
            '-location__is_active',  # Active locations first
            'location__name',
            '-is_active',           # Active devices first
            'name',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        place_slug = self.kwargs.get('place_slug')
        location_pk = self.kwargs.get('location_pk')
        
        place = get_object_or_404(Place, slug=place_slug)
        context['place'] = place
        context['active_tab'] = 'devices'  # Set active tab for devices
        
         # Get locations for this place with correct device count annotations
        context['locations'] = Location.objects.filter(place=place).prefetch_related(
            'devices'
        ).annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        )
        
        if location_pk:
            location = get_object_or_404(locations, pk=location_pk)
            context['location'] = location
            
            # Get other devices for this location
            context['other_devices'] = self.get_queryset().filter(
                location=location
            ).exclude(
                pk__in=[d.pk for d in context['devices']] if 'devices' in context else []
            )
    
        return context

class DeviceDetailView(DetailView):
    model = Device
    context_object_name = 'device'
    template_name = 'sensors/device_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['active_tab'] = 'devices'
        
        device = self.get_object()
        location = device.location
        place = location.place
        
        context['location'] = location
        context['place'] = place
        
        # Get locations for this place with correct device count annotations
        context['locations'] = Location.objects.filter(place=place).prefetch_related(
            'devices'
        ).annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        )
        context['sensors'] = device.sensors.all()

        # Get other devices for this location
        context['other_devices'] = Device.objects.filter(
            location=location
        ).exclude(
            pk=device.pk
        ).select_related(
            'location'
        ).prefetch_related(
            'sensors'
        ).annotate(
            active_sensors=Count('sensors', filter=Q(sensors__is_active=True)),
            total_sensors=Count('sensors')
        )
        
        return context

class DeviceCreateView(SuccessMessageMixin, CreateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'
    success_message = "Device %(name)s was created successfully"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Add referrer to form kwargs
        referrer = self.request.META.get('HTTP_REFERER')
        if referrer:
            kwargs['referrer'] = referrer
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        
        place_slug = self.kwargs.get('place_slug')
        location_pk = self.kwargs.get('location_pk')
        
        place = get_object_or_404(Place, slug=place_slug)
        context['place'] = place
        
        # Get locations for this place
        locations = Location.objects.filter(place=place).prefetch_related(
            'devices'
        ).annotate(
            active_devices=Count('devices', filter=Q(devices__is_active=True)),
            total_devices=Count('devices')
        )
        context['locations'] = locations
        
        if location_pk:
            location = get_object_or_404(locations, pk=location_pk)
            context['location'] = location
            
            # Get devices for this location
            context['devices'] = Device.objects.filter(
                location=location
            ).select_related(
                'location'
            ).prefetch_related(
                'sensors'
            ).annotate(
                active_sensors=Count('sensors', filter=Q(sensors__is_active=True)),
                total_sensors=Count('sensors')
            )
            
            context['location_url'] = reverse('sensors:location_detail', kwargs={
                'place_slug': place_slug,
                'pk': location_pk
            })
        
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
            form.fields['is_active'].initial = False
        return form

    def form_valid(self, form):
        location_pk = self.kwargs.get('location_pk')
        location = get_object_or_404(Location, pk=location_pk)
        form.instance.location = location
        response = super().form_valid(form)
        success_message = self.get_success_message(form.cleaned_data)
        messages.success(self.request, success_message)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'redirect_url': self.get_success_url()
            })
        return response

    def get_success_url(self):
        # Try to get the referrer from the form data
        referrer = self.request.POST.get('referrer')
        if referrer:
            return referrer
            
        # Fall back to the default URL if no referrer
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.kwargs.get('place_slug'),
            'pk': self.object.pk
        })

class DeviceUpdateView(UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Add referrer to form kwargs
        referrer = self.request.META.get('HTTP_REFERER')
        if referrer:
            kwargs['referrer'] = referrer
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        
        device = self.get_object()
        location = device.location
        place = location.place
        
        context['device'] = device
        context['location'] = location
        context['place'] = place
        
        # Get locations for this place
        context['locations'] = Location.objects.filter(place=place).prefetch_related(
            'devices'
        ).annotate(
            active_devices=Count('devices', filter=Q(devices__is_active=True)),
            total_devices=Count('devices')
        )
        
        # Get other devices for this location
        context['other_devices'] = Device.objects.filter(
            location=location
        ).exclude(
            pk=device.pk
        ).select_related(
            'location'
        ).prefetch_related(
            'sensors'
        ).annotate(
            active_sensors=Count('sensors', filter=Q(sensors__is_active=True)),
            total_sensors=Count('sensors')
        )
        
        context['location_url'] = reverse('sensors:location_detail', kwargs={
            'place_slug': place.slug,
            'pk': location.pk
        })
        
        return context

    def get_initial(self):
        initial = super().get_initial()
        initial['place_slug'] = self.kwargs.get('place_slug')
        initial['location_pk'] = self.kwargs.get('location_pk')
        return initial

    def get_success_url(self):
        # Try to get the referrer from the form data
        referrer = self.request.POST.get('referrer')
        if referrer:
            return referrer
            
        # Fall back to the default URL if no referrer
        device = self.get_object()
        return reverse('sensors:device_detail', kwargs={
            'place_slug': device.location.place.slug,
            'pk': device.pk
        })

    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Handle inactive state after save
        if not form.instance.is_active:
            self.object.sensors.all().update(is_active=False)
        
        # Create path string with icons
        device = self.object
        location = device.location
        place = location.place
        path = f'<i class="bi bi-house-gear"></i> {place.name} > <i class="bi bi-geo-alt"></i> {location.name} > <i class="bi bi-hdd-rack"></i> {device.name}'
        
        # Create status message
        status_text = "active" if form.instance.is_active else "inactive"
        message = f'Device updated: {path} ({status_text})'
        
        # Get or initialize toast history
        toast_history = self.request.session.get('toast_history', [])
        
        # Create toast data
        toast_data = {
            'id': f'device_update_{device.pk}_{int(time.time())}',
            'title': 'Device Update',
            'message': message,
            'type': 'success',
            'timestamp': timezone.now().isoformat(),
            'addToHistory': True
        }
        
        # Add to history
        toast_history.append(toast_data)
        
        # Trim history to last 50 items
        toast_history = toast_history[-50:]
        
        # Update session
        self.request.session['toast_history'] = toast_history
        self.request.session.modified = True
            
        # Return JSON for AJAX requests
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'type': 'success',
                'message': message,
                'title': 'Device Update',
                'addToHistory': True,
                'id': toast_data['id'],
                'timestamp': toast_data['timestamp'],
                'redirect_url': self.get_success_url()
            })
        
        # For non-AJAX requests, add to messages
        messages.success(self.request, message)
        return response

class DeviceDeleteView(DeleteView):
    model = Device
    template_name = 'sensors/device_confirm_delete.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        
        device = self.get_object()
        location = device.location
        place = location.place
        
        context['device'] = device
        context['location'] = location
        context['place'] = place
        
        # Get locations for this place
        context['locations'] = Location.objects.filter(place=place).prefetch_related(
            'devices'
        ).annotate(
            active_devices=Count('devices', filter=Q(devices__is_active=True)),
            total_devices=Count('devices')
        )
        
        # Get other devices for this location
        context['other_devices'] = Device.objects.filter(
            location=location
        ).exclude(
            pk=device.pk
        ).select_related(
            'location'
        ).prefetch_related(
            'sensors'
        ).annotate(
            active_sensors=Count('sensors', filter=Q(sensors__is_active=True)),
            total_sensors=Count('sensors')
        )
        
        context['location_url'] = reverse('sensors:location_detail', kwargs={
            'place_slug': place.slug,
            'pk': location.pk
        })
        return context

    def get_success_url(self):
        device = self.get_object()
        return reverse('sensors:location_detail', kwargs={
            'place_slug': device.location.place.slug,
            'pk': device.location.pk
        })

    def delete(self, request, *args, **kwargs):
        device = self.get_object()
        success_url = self.get_success_url()
        response = super().delete(request, *args, **kwargs)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': f"Device {device.name} was deleted successfully",
                'redirect_url': success_url
            })
        return response

# Sensor Views
class SensorListView(ListView):
    model = Sensor
    context_object_name = 'sensors'
    template_name = 'sensors/sensor_list.html'

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        place_slug = self.kwargs.get('place_slug')
        location_pk = self.kwargs.get('location_pk')
        device_pk = self.kwargs.get('device_pk')
        
        if place_slug:
            queryset = queryset.filter(device__location__place__slug=place_slug)
            if location_pk:
                queryset = queryset.filter(device__location_id=location_pk)
            if device_pk:
                queryset = queryset.filter(device_id=device_pk)

        return queryset.select_related(
            'device', 
            'device__location', 
            'device__location__place'
        ).order_by(
            '-device__location__is_active',  # Active locations first
            'device__location__name',
            '-device__is_active',           # Active devices first
            'device__name',
            '-is_active',                   # Active sensors first
            'name'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        
        place_slug = self.kwargs.get('place_slug')
        location_pk = self.kwargs.get('location_pk')
        device_pk = self.kwargs.get('device_pk')
        
        if place_slug:
            place = get_object_or_404(Place, slug=place_slug)
            context['place'] = place
            
            # Get locations with prefetched devices and their device counts
            locations = Location.objects.filter(place=place).prefetch_related(
                'devices'
            ).annotate(
                active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
                inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
            )
            context['locations'] = locations
            
            # Get devices filtered by location if provided
            devices_query = Device.objects.filter(location__place=place)
            if location_pk:
                context['location'] = get_object_or_404(locations, pk=location_pk)
                devices_query = devices_query.filter(location_id=location_pk)
            
            # Annotate devices with sensor counts
            devices = devices_query.select_related(
                'location'
            ).prefetch_related(
                'sensors'
            ).annotate(
                active_sensors=Count('sensors', filter=Q(sensors__is_active=True)),
                total_sensors=Count('sensors')
            )
            
            if device_pk:
                context['device'] = get_object_or_404(devices, pk=device_pk)
            else:
                context['devices'] = devices

        return context

class SensorDetailView(DetailView):
    model = Sensor
    context_object_name = 'sensor'
    template_name = 'sensors/sensor_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        
        sensor = self.get_object()
        device = sensor.device
        location = device.location
        place = location.place
        
        context['device'] = device
        context['location'] = location
        context['place'] = place
        
        # Get locations with prefetched devices and their sensor counts
        locations = Location.objects.filter(place=place).prefetch_related(
            'devices'
        ).annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        )
        context['locations'] = locations
        
        # Get devices for this location
        context['devices'] = Device.objects.filter(
            location=location
        ).select_related(
            'location'
        ).prefetch_related(
            'sensors'
        ).annotate(
            total_active_sensors=Count('sensors', filter=Q(sensors__is_active=True)),
            total_inactive_sensors=Count('sensors', filter=Q(sensors__is_active=False))
        )
        
        context['influx_readings'] = get_sensor_readings(
            sensor=sensor,
            limit=100
        )
        return context

class SensorCreateView(SuccessMessageMixin, CreateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'
    success_message = "Sensor %(name)s was created successfully"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        device = get_object_or_404(Device, pk=self.kwargs.get('device_pk'))
        kwargs['device'] = device
        # Add referrer to form kwargs
        referrer = self.request.META.get('HTTP_REFERER')
        if referrer:
            kwargs['referrer'] = referrer
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        
        place_slug = self.kwargs.get('place_slug')
        place = get_object_or_404(Place, slug=place_slug)
        context['place'] = place
        
        device_pk = self.kwargs.get('device_pk')
        device = get_object_or_404(Device, pk=device_pk)
        context['device'] = device
        
        location = device.location
        context['location'] = location
        # Get locations with prefetched devices and their sensor counts
        locations = Location.objects.filter(place=place).prefetch_related(
            'devices'
        ).annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        )
        context['locations'] = locations
        
        return context

    def form_valid(self, form):
        device = get_object_or_404(Device, pk=self.kwargs.get('device_pk'))
        form.instance.device = device
        response = super().form_valid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': self.get_success_message(form.cleaned_data),
                'redirect_url': self.get_success_url()
            })
        return response

    def get_success_url(self):
        # Try to get the referrer from the form data
        referrer = self.request.POST.get('referrer')
        if referrer:
            return referrer
            
        # Fall back to the default URL if no referrer
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.kwargs.get('place_slug'),
            'pk': self.kwargs.get('device_pk')
        })

class SensorUpdateView(SuccessMessageMixin, UpdateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'
    success_message = "Sensor %(name)s was updated successfully"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Add referrer to form kwargs
        referrer = self.request.META.get('HTTP_REFERER')
        if referrer:
            kwargs['referrer'] = referrer
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        sensor = self.get_object()

        place_slug = self.kwargs.get('place_slug')
        place = get_object_or_404(Place, slug=place_slug)
        context['place'] = place

        location = sensor.device.location
        device = sensor.device
        context['location'] = location
        context['device'] = device

        # Get locations with prefetched devices and their sensor counts
        locations = Location.objects.filter(place=place).prefetch_related(
            'devices'
        ).annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        )
        context['locations'] = locations
        
        # Get devices for this location
        context['devices'] = Device.objects.filter(location=location
            ).select_related(
            'location'
        ).prefetch_related(
            'sensors'
        ).annotate(
            active_sensors=Count('sensors', filter=Q(sensors__is_active=True)),
            total_sensors=Count('sensors')
        )
        
        context['device_url'] = reverse('sensors:device_detail', kwargs={
            'place_slug': place.slug,
            'pk': device.pk
        })
        return context

    def get_success_url(self):
        # Try to get the referrer from the form data
        referrer = self.request.POST.get('referrer')
        if referrer:
            return referrer
            
        # Fall back to the default URL if no referrer
        sensor = self.get_object()
        return reverse('sensors:device_detail', kwargs={
            'place_slug': sensor.device.location.place.slug,
            'pk': sensor.device.pk
        })

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': self.get_success_message(form.cleaned_data),
                'redirect_url': self.get_success_url()
            })
        return response

class SensorDeleteView(DeleteView):
    model = Sensor
    template_name = 'sensors/sensor_confirm_delete.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Store the referrer URL in session if it's not from our success URL
        referrer = request.META.get('HTTP_REFERER')
        if referrer and not referrer.endswith(self.get_success_url()):
            request.session['sensor_redirect_url'] = referrer
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        sensor = self.get_object()

        place_slug = self.kwargs.get('place_slug')
        place = get_object_or_404(Place, slug=place_slug)
        context['place'] = place

        context['location'] = sensor.device.location
        context['device'] = sensor.device

        context['device_url'] = reverse('sensors:device_detail', kwargs={
            'place_slug': place.slug,
            'pk': context['device'].pk
        })
        return context

    def get_success_url(self):
        # Try to get the stored referrer URL from session
        if 'sensor_redirect_url' in self.request.session:
            success_url = self.request.session.pop('sensor_redirect_url')
            return success_url
            
        # Fall back to the default URL if no referrer stored
        place_slug = self.kwargs.get('place_slug')
        place = get_object_or_404(Place, slug=place_slug)
        return reverse('sensors:device_detail', kwargs={
            'place_slug': place.slug,
            'pk': self.get_object().device.pk
        })

    def delete(self, request, *args, **kwargs):
        sensor = self.get_object()
        success_url = self.get_success_url()
        response = super().delete(request, *args, **kwargs)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': f"Sensor {sensor.name} was deleted successfully",
                'redirect_url': success_url
            })
        return response

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
        context['model_name'] = 'reading'
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
        context['model_name'] = 'reading'
        # Add InfluxDB detailed data for this reading
        return context

class SensorReadingCreateView(SuccessMessageMixin, CreateView):
    model = SensorReading
    fields = ['sensor', 'value', 'notes']
    template_name = 'sensors/reading_form.html'
    success_message = "Reading for %(sensor)s was created successfully"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'reading'
        return context

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

class SensorToggleActiveView(View):
    def post(self, request, place_slug, pk):
        sensor = get_object_or_404(Sensor, pk=pk,
                                 device__location__place__slug=place_slug)
        
        try:
            data = json.loads(request.body)
            is_active = data.get('is_active', False)
            
            # Update sensor status
            sensor.is_active = is_active
            sensor.save()
            
            # Get updated statistics
            device = sensor.device
            total_sensors = device.sensors.count()
            active_sensors = device.sensors.filter(is_active=True).count()
            
            # Create descriptive message with full path and icons
            message = (
                f'<i class="bi bi-house-gear"></i> {sensor.device.location.place.name} &gt; '
                f'<i class="bi bi-geo-alt"></i> {sensor.device.location.name} &gt; '
                f'<i class="bi bi-hdd-rack"></i> {sensor.device.name} &gt; '
                f'<i class="bi bi-thermometer"></i> {sensor.name} '
                f'{is_active and "activated" or "deactivated"}'
            )
            
            return JsonResponse({
                'status': 'success',
                'message': message,
                'is_active': sensor.is_active,
                'total_sensors': total_sensors,
                'active_sensors': active_sensors,
                'device_id': device.pk,
                'type': 'success' if is_active else 'danger'  # Set toast type based on activation status
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class DeviceToggleActiveView(View):
    def post(self, request, place_slug, pk):
        device = get_object_or_404(Device, pk=pk)
        
        try:
            data = json.loads(request.body)
            is_active = data.get('is_active', False)
            
            # If deactivating, get list of active sensors first
            affected_sensors = []
            if not is_active:
                affected_sensors = list(device.sensors.filter(is_active=True).values('name', 'sensor_type'))
            
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
            active_devices_count = Device.objects.filter(
                location__place=location.place,
                is_active=True
            ).count()
            
            # Create descriptive message with full path and icons
            message = (
                f'<i class="bi bi-house-gear"></i> {location.place.name} &gt; '
                f'<i class="bi bi-geo-alt"></i> {location.name} &gt; '
                f'<i class="bi bi-hdd-rack"></i> {device.name} '
                f'{is_active and "activated" or "deactivated"}'
            )
            
            # If sensors were affected, add them to the message
            if affected_sensors:
                message += '<br><br>The following sensors were deactivated:'
                message += '<ul class="mb-0">'
                for sensor in affected_sensors:
                    message += f'<li><i class="bi bi-thermometer"></i> {sensor["name"]} ({sensor["sensor_type"]})</li>'
                message += '</ul>'
            
            return JsonResponse({
                'status': 'success',
                'message': message,
                'is_active': device.is_active,
                'active_devices_count': active_devices_count,
                'inactive_devices_count': inactive_devices_count,
                'active_devices_count': active_devices_count,
                'location_id': location.pk,
                'affected_sensors': affected_sensors,
                'type': 'success' if is_active else 'warning'  # Set toast type based on activation status and affected sensors
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class DeviceActiveSensorsView(View):
    def get(self, request, place_slug, pk):
        device = get_object_or_404(Device, pk=pk)
        ic(place_slug, device)
        try:

            active_sensors = device.sensors.filter(is_active=True)
            
            sensors_data = [{
                'name': sensor.name,
                'type': sensor.sensor_type if sensor.sensor_type else 'Unknown',
                'id': sensor.pk
            } for sensor in active_sensors]
            
            return JsonResponse({
                'status': 'success',
                'sensors': sensors_data
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

class DeviceMoveLocationView(View):
    def post(self, request, pk):
        # Get the device and validate it exists
        device = get_object_or_404(Device, pk=pk)
        
        try:
            data = json.loads(request.body)
            new_location_id = data.get('new_location_id')
            # 'new_location_id', new_location_id)
            if not new_location_id:
                return JsonResponse({'error': 'new_location_id is required'}, status=400)
            
            # Get the new location and validate it exists
            new_location = get_object_or_404(Location, pk=new_location_id)
            # 'new_location', new_location)
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
            # 'saved device.location', device.location)
            # Get updated counts
            old_location_count = old_location.devices.filter(is_active=True).count()
            new_location_count = new_location.devices.filter(is_active=True).count()
            results = JsonResponse({
                'success': True,
                'new_location_name': new_location.name,
                'old_location_count': old_location_count,
                'new_location_count': new_location_count,
                'active_devices_count': Device.objects.filter(
                    location__place=device.location.place,
                    is_active=True
                ).count()
            })
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

@require_POST
def location_toggle_active(request, place_slug, pk):
    """Toggle location active status"""
    location = get_object_or_404(Location, pk=pk)
    
    try:
        data = json.loads(request.body)
        is_active = data.get('is_active', False)
        
        # Update location status
        location.is_active = is_active
        location.save()
        
        # If location is set to inactive, cascade to all devices
        if not is_active:
            location.devices.all().update(is_active=False)
        
        return JsonResponse({
            'status': 'success',
            'is_active': location.is_active
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

class ToastHistoryView(View):
    """API view for managing toast notification history in the session."""
    
    def get(self, request):
        """Retrieve the toast history from the session."""
        history = request.session.get('toast_history', [])
        return JsonResponse({'history': history})

    def post(self, request):
        """Update the toast history in the session."""
        try:
            data = json.loads(request.body)
            history = data.get('history', [])
            
            # Ensure history doesn't exceed maximum size (50 items)
            history = history[:50]
            
            # Store in session
            request.session['toast_history'] = history
            request.session.modified = True
            
            return JsonResponse({
                'status': 'success',
                'message': 'Toast history updated successfully'
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

    def delete(self, request):
        """Clear the toast history from the session."""
        if 'toast_history' in request.session:
            del request.session['toast_history']
            request.session.modified = True
        
        return JsonResponse({
            'status': 'success',
            'message': 'Toast history cleared successfully'
        })
