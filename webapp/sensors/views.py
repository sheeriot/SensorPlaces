from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from .models import Place, Location, Device, Sensor, SensorReading
from .utils import get_sensor_readings  #, write_sensor_reading
from .forms import SensorForm, PlaceForm, DeviceForm, LocationForm
from .map_fun import place_map_create
from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponseRedirect
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from typing import Any, Dict, List, Optional, Type
from django.db.models.query import QuerySet
from django.db.models import Count, Q
from django.db.models.functions import Lower
import json
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
import time
from django.utils import timezone
import math
from geopy.distance import geodesic

from icecream import ic

def calculate_zoom(distance=0):
    """Calculate appropriate zoom level based on distance in kilometers"""
    if distance <= 0.4:
        return 16
    if distance <= 1:
        return 15
    if distance <= 2:
        return 14
    elif distance <= 4:
        return 13
    elif distance <= 10:
        return 12
    elif distance <= 17:
        return 11
    elif distance <= 30:
        return 10
    elif distance <= 60:
        return 9
    elif distance <= 120:
        return 8
    elif distance <= 250:
        return 7
    elif distance <= 550:
        return 6
    elif distance <= 1100:
        return 5
    elif distance <= 2000:
        return 4
    elif distance <= 5000:
        return 3
    else:
        return 2

# Place Views
class PlaceListView(ListView):
    model: Type[Place] = Place
    context_object_name = 'places'
    template_name = 'sensors/place_list.html'

    def get_queryset(self) -> QuerySet[Place]:
        ic("Getting places queryset")
        queryset = Place.objects.annotate(
            active_locations_count=Count('locations', filter=Q(locations__is_active=True)),
            active_devices_count=Count('locations__devices', filter=Q(locations__devices__is_active=True)),
            active_sensors_count=Count('locations__devices__sensors', filter=Q(locations__devices__sensors__is_active=True))
        ).order_by('-is_active', Lower('name'))
        ic("Places queryset count:", queryset.count())
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ic("Getting context data for place list")
        
        # Create map for all places
        places = self.get_queryset()
        ic("Creating map for places:", places.count())
        
        try:
            map_html = place_map_create(places=places)
            ic("Generated map HTML length:", len(map_html))
            context['place_map_html'] = map_html
        except Exception as e:
            ic("Error in map creation:", str(e))
            context['place_map_html'] = ""
        
        return context

class PlaceDetailView(DetailView):
    model: Type[Place] = Place
    context_object_name = 'place'
    template_name = 'sensors/place_detail.html'
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        place = get_object_or_404(Place, slug=self.kwargs.get('place_slug'))
        
        # Annotate locations with device counts
        locations = Location.objects.filter(place=place).annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        ).order_by('-is_active', 'name')
        context['locations'] = locations
        
        # Add device counts
        context.update({
            'devices_active': Device.objects.filter(location__place=place, is_active=True).count(),
            'devices_inactive': Device.objects.filter(location__place=place, is_active=False).count(),
            'sensors_active': Sensor.objects.filter(device__location__place=place, is_active=True).count(),
            'sensors_inactive': Sensor.objects.filter(device__location__place=place, is_active=False).count(),
        })
        
        return context

class PlaceCreateView(SuccessMessageMixin, CreateView):
    model: Type[Place] = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'

    def get_success_message(self, cleaned_data):
        place = self.object
        return (
            f"Created place <strong>{place.name}</strong><br>"
            f"<small class='text-muted'>"
            f"Location: ({place.latitude}, {place.longitude})<br>"
            f"Status: {'Active' if place.is_active else 'Inactive'}"
            f"</small>"
        )

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
        success_message = self.get_success_message(form.cleaned_data)
        
        # Add to toast history first
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'success',  # Always use success type for creation
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            self.request.session.modified = True

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'success',
                'redirect_url': self.get_success_url()
            })
        
        return response

class PlaceUpdateView(SuccessMessageMixin, UpdateView):
    model: Type[Place] = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'
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
        return context

    def form_valid(self, form):
        # Store original values before save
        self._original_values = {
            'name': self.get_object().name,
            'is_active': self.get_object().is_active,
            'latitude': self.get_object().latitude,
            'longitude': self.get_object().longitude,
            'slug': self.get_object().slug
        }
        response = super().form_valid(form)
        success_message = self.get_success_message(form.cleaned_data)
        
        # Add to toast history first
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'warning',  # Always use warning type for updates
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            self.request.session.modified = True

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'warning',
                'redirect_url': self.get_success_url()
            })
        
        return response

    def get_success_message(self, cleaned_data):
        place = self.object
        return (
            f"Updated place <strong>{place.name}</strong><br>"
            f"<small class='text-muted'>"
            f"Location: ({place.latitude}, {place.longitude})<br>"
            f"Status: {'Active' if place.is_active else 'Inactive'}"
            f"</small>"
        )

    def get_success_url(self):
        # Try to get the referrer from the form data
        referrer = self.request.POST.get('referrer')
        if referrer:
            return referrer
            
        # Fall back to the default URL if no referrer
        return reverse('sensors:place_list')

class PlaceDeleteView(DeleteView):
    model: Type[Place] = Place
    template_name = 'sensors/place_confirm_delete.html'
    success_url = reverse_lazy('sensors:place_list')
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'

    def delete(self, request, *args, **kwargs):
        place = self.get_object()
        success_url = str(self.success_url)
        
        # Create detailed message before deletion
        success_message = (
            f"Deleted place <strong>{place.name}</strong><br>"
            f"<small class='text-muted'>"
            f"Location: ({place.latitude}, {place.longitude})<br>"
            f"Status: {'Active' if place.is_active else 'Inactive'}"
            f"</small>"
        )
        
        place.delete()
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'danger',  # Always use danger type for deletion
                'redirect_url': success_url
            })
            
        # Add to toast history
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'danger',
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            
        return HttpResponseRedirect(success_url)

# Location Views
class LocationListView(ListView):
    model: Type[Location] = Location
    context_object_name = 'locations'
    template_name = 'sensors/location_list.html'

    def get_queryset(self):
        place_slug = self.kwargs.get('place_slug')
        return Location.objects.filter(place__slug=place_slug).order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        place = get_object_or_404(Place, slug=self.kwargs.get('place_slug'))
        context['place'] = place
        context['model_name'] = 'location'

        # Annotate locations with device counts
        locations = Location.objects.filter(place=place).annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        ).order_by('-is_active', 'name')
        context['locations'] = locations
        
        # Get any pending update message from the session
        ic("Checking session for location_update_message")
        if 'location_update_message' in self.request.session:
            toast_message = self.request.session.pop('location_update_message')
            ic("Found toast message in session:", toast_message)
            context['toast_message'] = toast_message
        else:
            ic("No toast message found in session")
        
        return context

class LocationDetailView(DetailView):
    model: Type[Location] = Location
    context_object_name = 'location'
    template_name = 'sensors/location_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        location = get_object_or_404(Location, pk=self.kwargs.get('pk'))
        place_slug = self.kwargs.get('place_slug')
        
        if place_slug:
            place = get_object_or_404(Place, slug=place_slug)
            context['place'] = place
            context['locations'] = Location.objects.filter(place=place).annotate(
                active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
                inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
            ).order_by('-is_active', 'name')
            context['devices'] = Device.objects.filter(location=location)
            for device in context['devices']:
                ic(vars(device))
        return context

class LocationCreateView(SuccessMessageMixin, CreateView):
    model: Type[Location] = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'

    def get_success_message(self, cleaned_data):
        place = get_object_or_404(Place, slug=self.kwargs.get('place_slug'))
        return (
            f"Created location <strong>{cleaned_data['name']}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name}<br>"
            f"<small class='text-muted'>"
            f"Status: {'Active' if cleaned_data['is_active'] else 'Inactive'}<br>"
            f"Devices: {cleaned_data['devices'].count()}"
            f"</small>"
        )

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
        success_message = self.get_success_message(form.cleaned_data)
        
        # Add to toast history first
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'success',  # Always use success type for creation
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            self.request.session.modified = True

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'success',
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
    model: Type[Location] = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'

    def form_valid(self, form):
        # Store original values before save
        self._original_values = {
            'name': self.get_object().name,
            'is_active': self.get_object().is_active
        }
        response = super().form_valid(form)
        success_message = self.get_success_message(form.cleaned_data)
        
        # Add to toast history first
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'warning',  # Always use warning type for updates
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            self.request.session.modified = True

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'warning',
                'redirect_url': self.get_success_url()
            })
        
        return response

    def get_success_message(self, cleaned_data):
        location = self.object
        place = location.place
        changes = []
        if hasattr(self, '_original_values'):
            if self._original_values['name'] != cleaned_data['name']:
                changes.append(f"name: {self._original_values['name']} → {cleaned_data['name']}")
            if self._original_values['is_active'] != cleaned_data['is_active']:
                changes.append(f"active: {self._original_values['is_active']} → {cleaned_data['is_active']}")
        
        message = (
            f"Updated location <strong>{cleaned_data['name']}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name}"
        )
        if changes:
            message += f"<br><small class='text-muted'>Changes: {', '.join(changes)}</small>"
        return message

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

class LocationDeleteView(DeleteView):
    model: Type[Location] = Location
    template_name = 'sensors/location_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        location = self.get_object()
        place = location.place
        success_url = self.get_success_url()
        
        # Create detailed message before deletion
        success_message = (
            f"Deleted location <strong>{location.name}</strong> from "
            f"<i class='bi bi-house-gear'></i> {place.name}<br>"
            f"<small class='text-muted'>"
            f"Status: {'Active' if location.is_active else 'Inactive'}<br>"
            f"Devices: {location.devices.count()}"
            f"</small>"
        )
        
        location.delete()
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'danger',  # Always use danger type for deletion
                'redirect_url': success_url
            })
            
        # Add to toast history
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'danger',
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            
        return HttpResponseRedirect(success_url)

# Device Views
class DeviceListView(ListView):
    model: Type[Device] = Device
    context_object_name = 'devices'
    template_name = 'sensors/device_list.html'

    def get_queryset(self) -> QuerySet[Device]:
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
    model: Type[Device] = Device
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
    model: Type[Device] = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'

    def get_success_message(self, cleaned_data):
        device = self.object
        location = device.location
        place = location.place
        return (
            f"Created device <strong>{device.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {device.device_type or '-'}<br>"
            f"Model: {device.model or '-'}<br>"
            f"Status: {'Active' if device.is_active else 'Inactive'}"
            f"</small>"
        )

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
        
        # Add to toast history first
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'success',  # Always use success type for creation
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            self.request.session.modified = True

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'success',
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

class DeviceUpdateView(SuccessMessageMixin, UpdateView):
    model: Type[Device] = Device
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
        device = self.get_object()
        location = device.location
        place = location.place
        context['place'] = place
        context['location'] = location
        context['model_name'] = 'device'
        
        # Get locations for this place with device counts
        context['locations'] = Location.objects.filter(place=place).prefetch_related(
            'devices'
        ).annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        )
        return context
    
    def form_valid(self, form):
        # Store original values before save
        self._original_values = {
            'name': self.get_object().name,
            'is_active': self.get_object().is_active,
            'location': self.get_object().location,
            'model': self.get_object().model,
            'manufacturer': self.get_object().manufacturer,
            'serial_number': self.get_object().serial_number,
            'device_type': self.get_object().device_type
        }
        response = super().form_valid(form)
        success_message = self.get_success_message(form.cleaned_data)

        # Add to toast history first
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'warning',  # Always use warning type for updates
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            self.request.session.modified = True

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            device = self.object
            location = device.location
            
            # Get updated statistics
            active_devices = location.devices.filter(is_active=True).count()
            total_devices = location.devices.count()
            
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'warning',
                'redirect_url': self.get_success_url(),
                'device': {
                    'id': device.pk,
                    'name': device.name,
                    'is_active': device.is_active,
                    'device_type': device.device_type,
                    'model': device.model,
                    'location': {
                        'id': location.pk,
                        'name': location.name,
                        'active_devices': active_devices,
                        'total_devices': total_devices
                    }
                }
            })

        return response

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'errors': form.errors,
                'message': 'Please correct the errors below.'
            }, status=400)
        return super().form_invalid(form)

    def get_success_message(self, cleaned_data):
        device = self.object
        location = device.location
        place = location.place
        changes = []
        
        if hasattr(self, '_original_values'):
            if self._original_values['name'] != device.name:
                changes.append(f"name from '{self._original_values['name']}' to '{device.name}'")
            
            if self._original_values['is_active'] != device.is_active:
                changes.append(f"status to {'active' if device.is_active else 'inactive'}")
            
            if self._original_values['location'] != device.location:
                changes.append(f"location from '{self._original_values['location'].name}' to '{device.location.name}'")
            
            if self._original_values['model'] != device.model:
                changes.append(f"model from '{self._original_values['model'] or '-'}' to '{device.model or '-'}'")
            
            if self._original_values['manufacturer'] != device.manufacturer:
                changes.append(f"manufacturer from '{self._original_values['manufacturer'] or '-'}' to '{device.manufacturer or '-'}'")
            
            if self._original_values['serial_number'] != device.serial_number:
                changes.append(f"serial number from '{self._original_values['serial_number'] or '-'}' to '{device.serial_number or '-'}'")
            
            if self._original_values.get('device_type') != device.device_type:
                changes.append(f"device type from '{self._original_values.get('device_type') or '-'}' to '{device.device_type or '-'}'")

        if changes:
            changes_text = ", ".join(changes)
            return (
                f"Updated device <strong>{device.name}</strong> in "
                f"<i class='bi bi-house-gear'></i> {place.name} > "
                f"<i class='bi bi-geo-alt'></i> {location.name}: {changes_text}"
            )
        return f"No changes made to device <strong>{device.name}</strong>"

    def get_success_url(self):
        # Try to get the referrer from the form data
        if self.request.POST.get('referrer'):
            return self.request.POST.get('referrer')
            
        # Fall back to the default URL if no referrer
        device = self.get_object()
        return reverse('sensors:device_detail', kwargs={
            'place_slug': device.location.place.slug,
            'pk': device.pk
        })

class DeviceDeleteView(DeleteView):
    model: Type[Device] = Device
    template_name = 'sensors/device_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        device = self.get_object()
        location = device.location
        place = location.place
        success_url = self.get_success_url()
        
        # Create detailed message before deletion
        success_message = (
            f"Deleted device <strong>{device.name}</strong> from "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {device.device_type or '-'}<br>"
            f"Model: {device.model or '-'}<br>"
            f"Status: {'Active' if device.is_active else 'Inactive'}<br>"
            f"Sensors: {device.sensors.count()}"
            f"</small>"
        )
        
        device.delete()
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'danger',  # Always use danger type for deletion
                'redirect_url': success_url
            })
            
        # Add to toast history
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'danger',
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            
        return HttpResponseRedirect(success_url)

# Sensor Views
class SensorListView(ListView):
    model: Type[Sensor] = Sensor
    context_object_name = 'sensors'
    template_name = 'sensors/sensor_list.html'

    def get_queryset(self) -> QuerySet[Sensor]:
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
    model: Type[Sensor] = Sensor
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
    model: Type[Sensor] = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'

    def get_success_message(self, cleaned_data):
        device = get_object_or_404(Device, pk=self.kwargs.get('device_pk'))
        location = device.location
        place = location.place
        return (
            f"Created sensor <strong>{cleaned_data['name']}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name} > "
            f"<i class='bi bi-hdd-rack'></i> {device.name}"
        )

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
        success_message = self.get_success_message(form.cleaned_data)
        
        # Add to toast history first
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'success',  # Always use success type for creation
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            self.request.session.modified = True

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'success',
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

class SensorUpdateView(SuccessMessageMixin, UpdateView):
    model: Type[Sensor] = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'

    def form_valid(self, form):
        # Store original values before save
        self._original_values = {
            'name': self.get_object().name,
            'is_active': self.get_object().is_active,
            'sensor_type': self.get_object().sensor_type,
            'device': self.get_object().device
        }
        response = super().form_valid(form)
        success_message = self.get_success_message(form.cleaned_data)
        
        # Add to toast history first
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'warning',  # Always use warning type for updates
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            self.request.session.modified = True

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'warning',
                'redirect_url': self.get_success_url()
            })
        
        return response

    def get_success_message(self, cleaned_data):
        sensor = self.object
        device = sensor.device
        location = device.location
        place = location.place
        changes = []
        if hasattr(self, '_original_values'):
            if self._original_values['name'] != cleaned_data['name']:
                changes.append(f"name: {self._original_values['name']} → {cleaned_data['name']}")
            if self._original_values['is_active'] != cleaned_data['is_active']:
                changes.append(f"active: {self._original_values['is_active']} → {cleaned_data['is_active']}")
            if self._original_values['sensor_type'] != cleaned_data['sensor_type']:
                changes.append(f"type: {self._original_values['sensor_type']} → {cleaned_data['sensor_type']}")
            if self._original_values['device'] != device:
                changes.append(f"device: {self._original_values['device'].name} → {device.name}")
        
        message = (
            f"Updated sensor <strong>{cleaned_data['name']}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name} > "
            f"<i class='bi bi-hdd-rack'></i> {device.name}"
        )
        if changes:
            message += f"<br><small class='text-muted'>Changes: {', '.join(changes)}</small>"
        return message

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        device = self.object.device
        kwargs['device'] = device
        # Add referrer to form kwargs
        referrer = self.request.META.get('HTTP_REFERER')
        if referrer:
            kwargs['referrer'] = referrer
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        
        sensor = self.get_object()
        device = sensor.device
        location = device.location
        place = location.place
        
        context['sensor'] = sensor
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

class SensorDeleteView(DeleteView):
    model: Type[Sensor] = Sensor
    template_name = 'sensors/sensor_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        sensor = self.get_object()
        device = sensor.device
        location = device.location
        place = location.place
        success_url = self.get_success_url()
        
        # Create detailed message before deletion
        success_message = (
            f"Deleted sensor <strong>{sensor.name}</strong> from "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name} > "
            f"<i class='bi bi-hdd-rack'></i> {device.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {sensor.sensor_type or '-'}<br>"
            f"Status: {'Active' if sensor.is_active else 'Inactive'}"
            f"</small>"
        )
        
        sensor.delete()
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': success_message,
                'type': 'danger',  # Always use danger type for deletion
                'redirect_url': success_url
            })
            
        # Add to toast history
        if hasattr(self.request, 'session'):
            toast_history = self.request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'danger',
                'timestamp': timezone.now().isoformat()
            })
            self.request.session['toast_history'] = toast_history
            
        return HttpResponseRedirect(success_url)

# SensorReading Views
class SensorReadingListView(ListView):
    model: Type[SensorReading] = SensorReading
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
    model: Type[SensorReading] = SensorReading
    context_object_name = 'reading'
    template_name = 'sensors/reading_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'reading'
        # Add InfluxDB detailed data for this reading
        return context

class SensorReadingCreateView(SuccessMessageMixin, CreateView):
    model: Type[SensorReading] = SensorReading
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
            
            # Add to toast history first
            if hasattr(request, 'session'):
                toast_history = request.session.get('toast_history', [])
                toast_history.append({
                    'message': message,
                    'type': 'warning',  # Always use warning type for device status changes
                    'timestamp': timezone.now().isoformat()
                })
                request.session['toast_history'] = toast_history
                request.session.modified = True
            
            return JsonResponse({
                'status': 'success',
                'message': message,
                'is_active': device.is_active,
                'active_devices_count': active_devices_count,
                'inactive_devices_count': inactive_devices_count,
                'active_devices_count': active_devices_count,
                'location_id': location.pk,
                'affected_sensors': affected_sensors,
                'type': 'warning'  # Ensure consistent warning type
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
def update_site_plan_layout(request, place_slug):
    """Update the site plan layout settings for a place"""
    if not request.user.has_perm('sensors.change_place'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
        
    place = get_object_or_404(Place, slug=place_slug)
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

class LocationToggleActiveView(View):
    def post(self, request: HttpRequest, place_slug: str, pk: int) -> JsonResponse:
        try:
            # Get the location and validate it exists
            location = get_object_or_404(Location.objects.select_related('place'), pk=pk)
            
            # Parse the intended state from request body
            data = json.loads(request.body)
            is_active = data.get('is_active', False)
            
            # Get affected devices before making any changes
            affected_devices = []
            if not is_active:
                affected_devices = list(location.devices.filter(is_active=True).values('name', 'model'))
            
            # Update location status
            location.is_active = is_active
            location.save()
            
            # If location is set to inactive, cascade to all devices and their sensors
            if not is_active:
                # Update all devices to inactive, which will cascade to sensors through device save method
                location.devices.all().update(is_active=False)
            
            # Get updated statistics
            active_devices = location.devices.filter(is_active=True).count()
            total_devices = location.devices.count()
            
            # Create descriptive message with full path and icons
            message = (
                f"{'Activated' if is_active else 'Deactivated'} location "
                f"<strong>{location.name}</strong> in "
                f"<i class='bi bi-house-gear'></i> {location.place.name}"
            )
            
            # Add affected devices to message if any
            if affected_devices:
                message += "<br><br>Affected devices:<ul class='mb-0'>"
                for device in affected_devices:
                    message += f"<li>{device['name']} ({device['model']})</li>"
                message += "</ul>"
            
            # Return success response with updated data
            return JsonResponse({
                'status': 'success',
                'message': message,
                'is_active': location.is_active,
                'affected_devices': affected_devices,
                'active_devices': active_devices,
                'total_devices': total_devices
            })
            
        except Location.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Location not found'
            }, status=404)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
