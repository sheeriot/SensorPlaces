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
from django.db.models import F, Subquery, OuterRef
from django.db.models.expressions import Value
import json
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
import time
from django.utils import timezone
import math
from geopy.distance import geodesic
from django.db.models.query import Prefetch

from icecream import ic

# Add the mixin first, before any classes that use it
class LocationAnnotationMixin:
    """Mixin to add annotated locations to context data."""
    
    def get_annotated_locations(self, place: Place) -> QuerySet[Location]:
        """Get locations with device and sensor counts."""
        return Location.objects.filter(place=place).annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False)),
            active_sensors_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=True)),
            inactive_sensors_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=False))
        ).order_by('-is_active', Lower('name'))

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add annotated locations to context."""
        context = super().get_context_data(**kwargs)
        if hasattr(self, 'kwargs') and 'place_slug' in self.kwargs:
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            context['locations'] = self.get_annotated_locations(place)
            context['place'] = place
        return context

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
    model = Place
    context_object_name = 'places'
    template_name = 'sensors/place_list.html'
    
    def get_queryset(self) -> QuerySet[Place]:
        if not hasattr(self, '_queryset'):
            self._queryset = Place.objects.annotate(
                active_locations_count=Count('locations', filter=Q(locations__is_active=True)),
                active_devices_count=Count('locations__devices', filter=Q(locations__devices__is_active=True)),
                active_sensors_count=Count('locations__devices__sensors', filter=Q(locations__devices__sensors__is_active=True))
            ).order_by('-is_active', Lower('name'))
            ic("Places Count:", self._queryset.count())
        return self._queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
        try:
            map_html = place_map_create(places=self.get_queryset())
            context['place_map_html'] = map_html
        except Exception as e:
            ic("Error in map creation:", str(e))
            context['place_map_html'] = ""
        
        return context

class PlaceDetailView(DetailView):
    model = Place
    context_object_name = 'place'
    template_name = 'sensors/place_detail.html'
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'

    def get_queryset(self) -> QuerySet[Place]:
        if not hasattr(self, '_queryset'):
            self._queryset = Place.objects.annotate(
                active_locations_count=Count('locations', filter=Q(locations__is_active=True)),
                active_devices_count=Count('locations__devices', filter=Q(locations__devices__is_active=True)),
                active_sensors_count=Count('locations__devices__sensors', filter=Q(locations__devices__sensors__is_active=True))
            )
            ic("Place Detail Query Executed")
        return self._queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
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
    model = Place
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
    model = Place
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
class LocationListView(LocationAnnotationMixin, ListView):
    model = Location
    context_object_name = 'locations'
    template_name = 'sensors/location_list.html'

    def get_queryset(self) -> QuerySet[Location]:
        if not hasattr(self, '_queryset'):
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            self._queryset = Location.objects.filter(place=place).annotate(
                active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
                inactive_devices_count=Count('devices', filter=Q(devices__is_active=False)),
                active_sensors_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=True)),
                inactive_sensors_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=False))
            ).order_by('-is_active', Lower('name'))
            ic("Locations Count:", self._queryset.count())
        return self._queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        context['place'] = place

        # Add place statistics
        context.update({
            'devices_active': Device.objects.filter(location__place=place, is_active=True).count(),
            'devices_inactive': Device.objects.filter(location__place=place, is_active=False).count(),
            'sensors_active': Sensor.objects.filter(device__location__place=place, is_active=True).count(),
            'sensors_inactive': Sensor.objects.filter(device__location__place=place, is_active=False).count(),
        })
        
        return context

class LocationDetailView(LocationAnnotationMixin, DetailView):
    model = Location
    context_object_name = 'location'
    template_name = 'sensors/location_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        
        # Add annotated devices to context with proper prefetching
        context['devices'] = Device.objects.filter(
            location=self.object
        ).select_related(
            'device_type'
        ).prefetch_related(
            'sensors'
        ).annotate(
            active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)),
            inactive_sensors_count=Count('sensors', filter=Q(sensors__is_active=False))
        ).order_by(
            '-is_active', 
            Lower('name')
        )
        
        # Add device and sensor counts
        context.update({
            'devices_active': Device.objects.filter(location=self.object, is_active=True).count(),
            'devices_inactive': Device.objects.filter(location=self.object, is_active=False).count(),
            'sensors_active': Sensor.objects.filter(device__location=self.object, is_active=True).count(),
            'sensors_inactive': Sensor.objects.filter(device__location=self.object, is_active=False).count(),
        })
        
        ic("Location Detail Device Query Executed")
        return context

class LocationCreateView(SuccessMessageMixin, CreateView):
    model = Location
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
    model = Location
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
    model = Location
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
class DeviceListView(LocationAnnotationMixin, ListView):
    model = Device
    context_object_name = 'devices'
    template_name = 'sensors/device_list.html'

    def get_queryset(self) -> QuerySet[Device]:
        if not hasattr(self, '_queryset'):
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            location_pk = self.kwargs.get('location_pk')
            
            base_queryset = super().get_queryset()
            queryset = base_queryset.filter(location__place=place)
            
            # Filter by location if specified
            if location_pk:
                queryset = queryset.filter(location_id=location_pk)
            
            # Add annotations and ordering
            self._queryset = queryset.select_related(
                'location', 
                'location__place'
            ).prefetch_related(
                Prefetch(
                    'sensors',
                    queryset=Sensor.objects.order_by('-is_active', Lower('name'))
                )
            ).annotate(
                active_sensors=Count('sensors', filter=Q(sensors__is_active=True)),
                total_sensors=Count('sensors')
            ).order_by(
                '-location__is_active',  # Active locations first
                'location__name',
                '-is_active',           # Active devices first
                'name'
            )
        return self._queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['place'] = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        
        # Add device and sensor counts
        queryset = self.get_queryset()
        context.update({
            'devices_active': queryset.filter(is_active=True).count(),
            'devices_inactive': queryset.filter(is_active=False).count(),
            'sensors_active': Sensor.objects.filter(
                device__in=queryset,
                is_active=True
            ).count(),
            'sensors_inactive': Sensor.objects.filter(
                device__in=queryset,
                is_active=False
            ).count(),
        })
        
        return context

class DeviceDetailView(LocationAnnotationMixin, DetailView):
    model = Device
    context_object_name = 'device'
    template_name = 'sensors/device_detail.html'

    def get_queryset(self) -> QuerySet[Device]:
        if not hasattr(self, '_queryset'):
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            base_queryset = super().get_queryset()
            self._queryset = base_queryset.filter(location__place=place)\
                .annotate(active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)))\
                .prefetch_related(
                    Prefetch(
                        'sensors',
                        queryset=Sensor.objects.order_by('-is_active', Lower('name'))
                    ))
        return self._queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['place'] = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        return context

class DeviceCreateView(LocationAnnotationMixin, LoginRequiredMixin, CreateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'

    def setup(self, request, *args, **kwargs):
        """Cache common values during view setup"""
        super().setup(request, *args, **kwargs)
        self._place = None
        self._location = None
        self._locations = None

    @property
    def place(self):
        """Cached place getter"""
        if self._place is None:
            place_slug = self.kwargs.get('place_slug')
            self._place = get_object_or_404(Place, slug=place_slug)
        return self._place

    @property
    def location(self):
        """Cached location getter"""
        if self._location is None:
            location_pk = self.kwargs.get('location_pk')
            if location_pk:
                self._location = get_object_or_404(Location, pk=location_pk, place=self.place)
        return self._location

    @property
    def locations(self):
        """Cached locations getter with annotations"""
        if self._locations is None:
            self._locations = Location.objects.filter(place=self.place).annotate(
                active_devices_count=Count(
                    'devices',
                    filter=Q(devices__is_active=True)
                ),
                inactive_devices_count=Count(
                    'devices',
                    filter=Q(devices__is_active=False)
                )
            ).select_related('place').prefetch_related(
                'devices',
                'devices__device_type'
            ).order_by('name')
        return self._locations

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = {
            'place': self.place,
            'location': self.location
        }
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['place'] = self.place
        context['locations'] = self.locations
        
        if self.location:
            context['location'] = self.location
        
        return context

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

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

    def get_queryset(self) -> QuerySet[Device]:
        if not hasattr(self, '_queryset'):
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            base_queryset = super().get_queryset()
            
            # Get sensors ordered properly
            sensors = Sensor.objects.filter(
                device=OuterRef('pk')
            ).order_by('-is_active', Lower('name')).values_list('pk', flat=True)

            self._queryset = base_queryset.filter(location__place=place).annotate(
                active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)),
                sensor_list=Subquery(sensors))
        return self._queryset

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
    
    try:
        place = get_object_or_404(Place, slug=place_slug)
        ic("Processing update for place:", place.name)
        
        data = json.loads(request.body)
        ic("Received data:", data)
        
        # Track site plan changes
        site_plan_changes = []
        
        # Check and update site plan transform
        if 'site_plan_scale' in data:
            old_scale = place.site_plan_scale
            place.site_plan_scale = float(data['site_plan_scale'])
            if old_scale != place.site_plan_scale:
                site_plan_changes.append(f"scale: {old_scale:.2f} → {place.site_plan_scale:.2f}")
        
        if 'site_plan_x' in data:
            old_x = place.site_plan_x
            place.site_plan_x = float(data['site_plan_x'])
            if old_x != place.site_plan_x:
                site_plan_changes.append(f"x offset: {old_x:.1f} → {place.site_plan_x:.1f}")
        
        if 'site_plan_y' in data:
            old_y = place.site_plan_y
            place.site_plan_y = float(data['site_plan_y'])
            if old_y != place.site_plan_y:
                site_plan_changes.append(f"y offset: {old_y:.1f} → {place.site_plan_y:.1f}")
        
        if site_plan_changes:
            place.save(update_fields=['site_plan_scale', 'site_plan_x', 'site_plan_y'])
        
        # Track location updates
        location_updates = []
        location_changes = data.get('locations', [])
        ic("Location updates to process:", len(location_changes))
        
        for update in location_changes:
            location_id = update.get('id')
            new_x = update.get('x')
            new_y = update.get('y')
            
            ic("Processing location update:", {
                'id': location_id,
                'new_x': new_x,
                'new_y': new_y
            })
            
            if location_id and new_x is not None and new_y is not None:
                location = Location.objects.filter(id=location_id, place=place).first()
                if location:
                    ic("Found location:", location.name)
                    old_x = float(location.x_coord) if location.x_coord is not None else 0
                    old_y = float(location.y_coord) if location.y_coord is not None else 0
                    new_x = float(new_x)
                    new_y = float(new_y)
                    
                    if old_x != new_x or old_y != new_y:
                        location_updates.append({
                            'name': location.name,
                            'old_pos': {'x': old_x, 'y': old_y},
                            'new_pos': {'x': new_x, 'y': new_y}
                        })
                        location.x_coord = new_x
                        location.y_coord = new_y
                        location.save(update_fields=['x_coord', 'y_coord'])
                        ic(f"Updated location {location.name} position")
                else:
                    ic(f"Location not found for ID: {location_id}")
        
        # Construct response message
        message = [f"Updated site plan layout for <strong>{place.name}</strong>"]
        
        if site_plan_changes:
            message.append("<br><small class='text-muted'>Site Plan Changes:")
            changes_with_icon = [f"<i class='bi bi-house-gear'></i> {change}" for change in site_plan_changes]
            message.append(", ".join(changes_with_icon))
            message.append("</small>")
        
        if location_updates:
            message.append("<br><small class='text-muted'>Location Changes:")
            for update in location_updates:
                message.append(
                    f"<br><i class='bi bi-geo-alt'></i> {update['name']}: "
                    f"({update['old_pos']['x']:.1f}, {update['old_pos']['y']:.1f}) → "
                    f"({update['new_pos']['x']:.1f}, {update['new_pos']['y']:.1f})"
                )
            message.append("</small>")
        
        final_message = "".join(message)
        
        response_data = {
            'status': 'success',
            'message': final_message,
            'type': 'warning',
            'messages': [{                       # Add messages array for toast history
                'message': final_message,
                'tags': 'warning safe',          # Include both warning and safe tags
                'level': messages.WARNING
            }],
            'changes': {
                'site_plan': {
                    'scale': place.site_plan_scale,
                    'x': place.site_plan_x,
                    'y': place.site_plan_y,
                    'changed': bool(site_plan_changes)
                },
                'locations': location_updates
            }
        }
        
        ic("Sending response:", response_data)
        return JsonResponse(response_data)
        
    except (ValueError, json.JSONDecodeError) as e:
        error_message = f'Invalid data format: {str(e)}'
        return JsonResponse({
            'error': error_message,
            'type': 'danger',
            'messages': [{                       # Add error message to history
                'message': error_message,
                'tags': 'error',
                'level': messages.ERROR
            }]
        }, status=400)
    except Exception as e:
        ic("Server error:", str(e))
        ic("Exception type:", type(e))
        ic("Exception traceback:", e.__traceback__)
        error_message = f'Server error: {str(e)}'
        return JsonResponse({
            'error': error_message,
            'type': 'danger',
            'messages': [{                       # Add error message to history
                'message': error_message,
                'tags': 'error',
                'level': messages.ERROR
            }]
        }, status=500)

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

class DeviceUpdateView(LocationAnnotationMixin, SuccessMessageMixin, UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['place'] = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        context['locations'] = Location.objects.filter(place=context['place']).order_by('-is_active', Lower('name'))
        return context
    
    def form_valid(self, form):
        # Store original values before save
        self._original_values = {
            'name': self.get_object().name,
            'is_active': self.get_object().is_active,
            'location': self.get_object().location,
            'device_type': self.get_object().device_type,
            'model': self.get_object().model
        }
        response = super().form_valid(form)
        success_message = self.get_success_message(form.cleaned_data)

        # Add to toast history
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
        device = self.object
        location = device.location
        place = location.place
        changes = []
        if hasattr(self, '_original_values'):
            if self._original_values['name'] != cleaned_data['name']:
                changes.append(f"name: {self._original_values['name']} → {cleaned_data['name']}")
            if self._original_values['is_active'] != cleaned_data['is_active']:
                changes.append(f"active: {self._original_values['is_active']} → {cleaned_data['is_active']}")
            if self._original_values['location'] != cleaned_data['location']:
                changes.append(f"location: {self._original_values['location'].name} → {cleaned_data['location'].name}")
            if self._original_values['device_type'] != cleaned_data['device_type']:
                changes.append(f"type: {self._original_values['device_type']} → {cleaned_data['device_type']}")
            if self._original_values['model'] != cleaned_data['model']:
                changes.append(f"model: {self._original_values['model']} → {cleaned_data['model']}")

        message = (
                f"Updated device <strong>{device.name}</strong> in "
                f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name}"
            )
        if changes:
            message += f"<br><small class='text-muted'>Changes: {', '.join(changes)}</small>"
        return message

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class DeviceDeleteView(DeleteView):
    model = Device
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

    def get_success_url(self):
        return reverse('sensors:place_devices', kwargs={'place_slug': self.object.location.place.slug})


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


class SensorCreateView(LocationAnnotationMixin, SuccessMessageMixin, CreateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'

    def setup(self, request, *args, **kwargs):
        """Cache common values during view setup"""
        super().setup(request, *args, **kwargs)
        self._place = None
        self._device = None

    @property
    def place(self):
        """Cached place getter"""
        if self._place is None:
            place_slug = self.kwargs.get('place_slug')
            self._place = get_object_or_404(Place, slug=place_slug)
        return self._place

    @property
    def device(self):
        """Cached device getter"""
        if self._device is None:
            device_pk = self.kwargs.get('device_pk')
            if device_pk:
                self._device = get_object_or_404(
                    Device.objects.select_related(
            'location'
                    ),
                    pk=device_pk,
                    location__place=self.place
                )
        return self._device

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = {
            'device': self.device,
            'is_active': True
        }
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        context['place'] = self.place
        
        if self.device:
            context['device'] = self.device
            context['location'] = self.device.location
        
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        success_message = self.get_success_message(form.cleaned_data)
        
        # Add to toast history
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

    def get_success_message(self, cleaned_data):
        sensor = self.object
        device = sensor.device
        location = device.location
        place = location.place
        return (
            f"Created sensor <strong>{sensor.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name} > "
            f"<i class='bi-hdd-rack'></i> {device.name}<br> > "
            f"<i class='bi bi-thermometer'></i> {sensor.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {sensor.sensor_type or '-'}<br>"
            f"Unit: {sensor.unit or '-'}<br>"
            f"Status: {'Active' if sensor.is_active else 'inactive'}"
            f"</small>"
        )

    def get_success_url(self):
        return reverse('sensors:sensor_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class SensorListView(LocationAnnotationMixin, ListView):
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
            
            # Apply ordering: active sensors first, then alphabetically by name
            self._queryset = self._queryset.order_by('-is_active', Lower('name'))
            
            # Prefetch related fields to avoid N+1 queries
            self._queryset = self._queryset.select_related(
                'device',
                'device__location',
                'device__location__place'
            )
            
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

class SensorDetailView(LocationAnnotationMixin, DetailView):
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
                ic(f"Error getting sensor readings: {str(e)}")
                context['readings_error'] = str(e)
        
        return context

class SensorUpdateView(LocationAnnotationMixin, SuccessMessageMixin, UpdateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        context['place'] = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        
        # Add device and location to context
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
            'unit': sensor.unit,
            'influx_measurement': getattr(sensor, 'influx_measurement', None),
            'influx_field': getattr(sensor, 'influx_field', None),
            'influx_filter_tags': getattr(sensor, 'influx_filter_tags', None)
        }
        response = super().form_valid(form)
        success_message = self.get_success_message(form.cleaned_data)
        
        # Add to toast history
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
            if self._original_values['device'] != cleaned_data['device']:
                changes.append(f"device: {self._original_values['device'].name} → {cleaned_data['device'].name}")
            if self._original_values['sensor_type'] != cleaned_data['sensor_type']:
                changes.append(f"type: {self._original_values['sensor_type']} → {cleaned_data['sensor_type']}")
            if self._original_values['data_type'] != cleaned_data['data_type']:
                changes.append(f"data source: {self._original_values['data_type']} → {cleaned_data['data_type']}")
            if self._original_values['unit'] != cleaned_data['unit']:
                changes.append(f"unit: {self._original_values['unit']} → {cleaned_data['unit']}")
            if self._original_values['influx_measurement'] != cleaned_data.get('influx_measurement'):
                changes.append(f"measurement: {self._original_values['influx_measurement']} → {cleaned_data.get('influx_measurement')}")
            if self._original_values['influx_field'] != cleaned_data.get('influx_field'):
                changes.append(f"field: {self._original_values['influx_field']} → {cleaned_data.get('influx_field')}")
            if self._original_values['influx_filter_tags'] != cleaned_data.get('influx_filter_tags'):
                changes.append(f"filter tags: {self._original_values['influx_filter_tags']} → {cleaned_data.get('influx_filter_tags')}")
        
        message = (
            f"Updated sensor <strong>{sensor.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name} > "
            f"<i class='bi bi-hdd-rack'></i> {device.name} > "
            f"<i class='bi bi-thermometer'></i> {sensor.name}"
        )
        if changes:
            message += f"<br><small class='text-muted'>Changes: {', '.join(changes)}</small>"
        return message

    def get_success_url(self):
        return reverse('sensors:sensor_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class SensorDeleteView(DeleteView):
    model = Sensor
    template_name = 'sensors/sensor_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        sensor = self.get_object()
        device = sensor.device
        location = device.location
        place = location.place
        success_url = self.get_success_url()
        
        # Create detailed message before deletion
        success_message = (
            f"Deleted sensor: "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name} > "
            f"<i class='bi bi-hdd-rack'></i> {device.name}<br> > "
            f"<i class='bi bi-thermometer'></i> {sensor.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {sensor.sensor_type or '-'}<br>"
            f"Unit: {sensor.unit or '-'}<br>"
            f"Data Source: {sensor.data_type}<br>"
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

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.device.pk
        })

class SensorReadingListView(ListView):
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

        return queryset.select_related('sensor', 'sensor__device', 'sensor__device__location', 'sensor__device__location__place').order_by('-timestamp')

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

class SensorReadingDetailView(DetailView):
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

class SensorReadingCreateView(LocationAnnotationMixin, SuccessMessageMixin, CreateView):
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
        success_message = self.get_success_message(form.cleaned_data)
        
        # Add to toast history
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

    def get_success_message(self, cleaned_data):
        reading = self.object
        sensor = reading.sensor
        device = sensor.device
        location = device.location
        place = location.place
        
        return (
            f"Created reading for sensor: "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name} > "
            f"<i class='bi bi-hdd-rack'></i> {device.name}<br> > "
            f"<i class='bi bi-thermometer'></i> {sensor.name}<br> "
            f"<small class='text-muted'>"
            f"Value: {reading.value} {sensor.unit or '-'}<br>"
            f"Timestamp: {reading.timestamp}"
            f"</small>"
        )

    def get_success_url(self):
        return reverse('sensors:sensor_reading_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'sensor_pk': self.sensor.pk,
            'pk': self.object.pk
        })

class SensorToggleActiveView(View):
    def post(self, request: HttpRequest, place_slug: str, pk: int) -> JsonResponse:
        try:
            # Get the sensor and validate it exists
            sensor = get_object_or_404(Sensor.objects.select_related('device', 'device__location', 'device__location__place'), pk=pk)
            
            # Parse the intended state from request body
            data = json.loads(request.body)
            is_active = data.get('is_active', False)
            
            # Update sensor status
            sensor.is_active = is_active
            sensor.save()
            
            # Get updated statistics
            active_sensors = sensor.device.sensors.filter(is_active=True).count()
            inactive_sensors = sensor.device.sensors.filter(is_active=False).count()
            active_sensors_place = Sensor.objects.filter(device__location__place__slug=place_slug, is_active=True).count()
            
            # Create descriptive message with full path and icons
            message = (
                f"{'Activated' if is_active else 'Deactivated'} sensor "
                f"<strong>{sensor.name}</strong> in "
                f"<i class='bi bi-house-gear'></i> {sensor.device.location.place.name} > "
                f"<i class='bi bi-geo-alt'></i> {sensor.device.location.name} > "
                f"<i class='bi bi-hdd-rack'></i> {sensor.device.name}"
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