from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from .models import Place, Location, Device, Sensor, SensorReading, ToastNotification
from .utils import get_sensor_readings, add_toast_message
from .forms import SensorForm, PlaceForm, DeviceForm, LocationForm, PlaceDeleteForm
from .map_fun import place_map_create
# from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponseRedirect
from django.views.decorators.http import require_POST
# from django.contrib.admin.views.decorators import staff_member_required
from typing import Any, Dict, List, Optional, Type
from django.db.models.query import QuerySet
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.db.models import F, Subquery, OuterRef
# from django.db.models.expressions import Value
import json
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
# import time
from django.utils import timezone
# import math
# from geopy.distance import geodesic
from django.db.models.query import Prefetch
from django.core.files.uploadedfile import UploadedFile
from decimal import Decimal
from icecream import ic
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import ImproperlyConfigured

# Add the mixin first, before any classes that use it
class LocationAnnotationMixin:
    """Mixin to add annotated locations to context data."""
    
    def get_place(self):
        """Get the place object from the URL kwargs.
        
        Raises:
            Http404: If place_slug is not in kwargs or Place does not exist
        """
        if not hasattr(self, '_place'):
            place_slug = self.kwargs.get('place_slug')
            if not place_slug:
                raise ImproperlyConfigured(
                    f"View {self.__class__.__name__} must be called with place_slug in URL kwargs"
                )
            self._place = get_object_or_404(Place, slug=place_slug)
        return self._place
    
    def get_location_data(self, location: Location) -> Dict[str, Any]:
        """Convert a Location instance to a JSON-serializable dictionary.
        
        Args:
            location: The Location model instance
            
        Returns:
            Dict containing the location data for JavaScript
        """
        return {
            'id': location.id,
            'name': location.name,
            'x_pos': float(location.x_pos) if isinstance(location.x_pos, Decimal) else location.x_pos,
            'y_pos': float(location.y_pos) if isinstance(location.y_pos, Decimal) else location.y_pos,
            'is_active': location.is_active,
            'active_devices_count': location.active_devices_count
        }

    def get_annotated_locations(self, place: Place) -> QuerySet[Location]:
        """Get annotated locations for a place.
        
        Args:
            place: The Place model instance
            
        Returns:
            QuerySet of Location instances with annotations
        """
        return Location.objects.filter(place=place).annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False)),
            active_sensors_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=True)),
            inactive_sensors_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=False))
        ).order_by('-is_active', Lower('name'))

    def get_context_data(self, **kwargs):
        """Add location data and place to the template context."""
        context = super().get_context_data(**kwargs)
        
        # Get place - this will always exist or raise an error
        place = self.get_place()
        context['place'] = place
        context['place_slug'] = place.slug
        
        # Get annotated locations for this place
        locations = self.get_annotated_locations(place)
        
        # Convert locations to JSON-serializable format for JavaScript
        locations_data = [self.get_location_data(loc) for loc in locations]
        
        # Add place statistics
        context.update({
            'locations': locations,  # Full queryset for template
            'locations_json': json.dumps(locations_data),  # JSON for JavaScript
            'devices_active': Device.objects.filter(location__place=place, is_active=True).count(),
            'devices_inactive': Device.objects.filter(location__place=place, is_active=False).count(),
            'sensors_active': Sensor.objects.filter(device__location__place=place, is_active=True).count(),
            'sensors_inactive': Sensor.objects.filter(device__location__place=place, is_active=False).count(),
        })
        
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
class PlaceListView(LoginRequiredMixin, ListView):
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
        return self._queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
        try:
            map_html = place_map_create(places=self.get_queryset())
            context['place_map_html'] = map_html
        except Exception as e:
            context['place_map_html'] = ""
        
        return context

class PlaceDetailView(LoginRequiredMixin, LocationAnnotationMixin, DetailView):
    model = Place
    context_object_name = 'place'
    template_name = 'sensors/place_detail.html'
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'

    def get_queryset(self) -> QuerySet[Place]:
        return Place.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'

        if 'locations' in context:
            locations_data = []
            for location in context['locations']:
                # Convert Decimal to float for JSON serialization
                x_pos = float(location.x_pos) if isinstance(location.x_pos, Decimal) else location.x_pos
                y_pos = float(location.y_pos) if isinstance(location.y_pos, Decimal) else location.y_pos
                
                locations_data.append({
                    'id': location.id,
                    'name': location.name,
                    'x_pos': x_pos,  # Match JavaScript property names
                    'y_pos': y_pos,  # Match JavaScript property names
                    'is_active': location.is_active,
                    'active_devices_count': location.active_devices_count
                })
            context['locations_json'] = json.dumps(locations_data)
            
        else:
            context['locations_json'] = '[]'
            
        return context

class PlaceCreateView(LoginRequiredMixin, CreateView):
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        place = self.object
        
        message = (
            f"Created place <strong>{place.name}</strong><br>"
            f"<small class='text-muted'>"
            f"Location: ({place.latitude}, {place.longitude})<br>"
            f"Status: {'Active' if place.is_active else 'Inactive'}"
            f"</small>"
        )
        
        self.request.toast_message = {
            'message': message,
            'type': 'success',
            'addToHistory': True
        }
        
        return response

    def get_success_url(self):
        return reverse('sensors:place_detail', kwargs={'place_slug': self.object.slug})

class PlaceUpdateView(LoginRequiredMixin, UpdateView):
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'
    slug_url_kwarg = 'place_slug'

    def get_initial(self):
        initial = super().get_initial()
        initial['referrer'] = self.request.META.get('HTTP_REFERER', '')
        return initial

    def get_success_url(self):
        if 'referrer' in self.request.POST:
            return self.request.POST['referrer']
        return reverse('sensors:place_list')

    def form_valid(self, form):
        original_values = {
            'name': self.get_object().name,
            'is_active': self.get_object().is_active,
            'latitude': self.get_object().latitude,
            'longitude': self.get_object().longitude,
            'siteplan_image': self.get_object().siteplan_image.name if self.get_object().siteplan_image else None
        }
        
        response = super().form_valid(form)
        
        # Build changes list
        changes = []
        if original_values['name'] != form.cleaned_data['name']:
            changes.append(f"name: {original_values['name']} → {form.cleaned_data['name']}")
        if original_values['is_active'] != form.cleaned_data['is_active']:
            changes.append(f"active: {original_values['is_active']} → {form.cleaned_data['is_active']}")
        if original_values['latitude'] != form.cleaned_data['latitude']:
            changes.append(f"latitude: {original_values['latitude']} → {form.cleaned_data['latitude']}")
        if original_values['longitude'] != form.cleaned_data['longitude']:
            changes.append(f"longitude: {original_values['longitude']} → {form.cleaned_data['longitude']}")
        
        # Check if siteplan image changed
        new_image = form.cleaned_data.get('siteplan_image')
        if new_image and original_values['siteplan_image'] != new_image.name:
            changes.append("siteplan image updated")
        
        message = (
            f"Updated place <strong>{form.cleaned_data['name']}</strong><br>"
            f"<small class='text-muted'>"
            f"Changes: {', '.join(changes) if changes else 'No changes'}"
            f"</small>"
        )
        
        self.request.toast_message = {
            'message': message,
            'type': 'warning',
            'addToHistory': True
        }
        
        return response

class PlaceDeleteView(LoginRequiredMixin, DeleteView):
    model = Place
    template_name = 'sensors/place_confirm_delete.html'
    success_url = reverse_lazy('sensors:place_list')
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'
    form_class = PlaceDeleteForm

    def delete(self, request, *args, **kwargs):
        place = self.get_object()
        success_url = self.get_success_url()
        
        # Build message before deletion
        message = (
            f"Deleted place <strong>{place.name}</strong><br>"
            f"<small class='text-muted'>"
            f"Location: ({place.latitude}, {place.longitude})<br>"
            f"Status: {'Active' if place.is_active else 'Inactive'}"
            f"</small>"
        )
        
        # Debug log before deletion
        # ic("PlaceDeleteView - Before delete:", {
        #     'place': place.name,
        #     'message': message
        # })
        
        # Perform deletion
        place.delete()
        
        # Set toast message - always set addToHistory to true
        # The toast-ui-manager will handle the presence/absence of the history button
        toast_data = {
            'message': message,
            'type': 'danger',
            'addToHistory': True  # Always true - UI will handle appropriately
        }
        
        self.request.toast_message = toast_data
        
        # Debug log after setting toast
        # ic("PlaceDeleteView - After setting toast:", {
        #     'toast_data': toast_data,
        #     'success_url': success_url
        # })
        
        return HttpResponseRedirect(success_url)

# Location Views
class LocationListView(LoginRequiredMixin, LocationAnnotationMixin, ListView):
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

class LocationDetailView(LoginRequiredMixin, LocationAnnotationMixin, DetailView):
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
        
        return context

class LocationCreateView(LoginRequiredMixin, LocationAnnotationMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'

    def get_success_url(self):
        return reverse('sensors:location_detail', kwargs={'place_slug': self.kwargs.get('place_slug'), 'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        place = get_object_or_404(Place, slug=self.kwargs.get('place_slug'))
        kwargs['initial'] = kwargs.get('initial', {})
        kwargs['initial']['place'] = place
        kwargs['initial']['referrer'] = self.request.GET.get('next', '')
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        return context

    def form_valid(self, form):
        place = get_object_or_404(Place, slug=self.kwargs.get('place_slug'))
        form.instance.place = place
        response = super().form_valid(form)
        location = self.object
        
        message = (
            f"Created location <strong>{location.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name}<br>"
            f"<small class='text-muted'>"
            f"Status: {'Active' if location.is_active else 'Inactive'}"
            f"</small>"
        )
        
        self.request.toast_message = {
            'message': message,
            'type': 'success',
            'addToHistory': True
        }
        
        return response

class LocationUpdateView(LoginRequiredMixin, LocationAnnotationMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'

    def get_success_url(self):
        return reverse('sensors:location_detail', kwargs={'place_slug': self.kwargs.get('place_slug'), 'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = kwargs.get('initial', {})
        kwargs['initial']['referrer'] = self.request.GET.get('next', '')
        return kwargs

    def form_valid(self, form):
        # Validate that place hasn't changed
        original_place_id = self.get_object().place_id
        if form.instance.place_id != original_place_id:
            form.add_error(None, "The place field cannot be modified after creation.")
            return self.form_invalid(form)
            
        self._original_values = {
            'name': self.get_object().name,
            'is_active': self.get_object().is_active
        }
        
        response = super().form_valid(form)
        location = self.object
        place = location.place
        changes = []
        
        if hasattr(self, '_original_values'):
            if self._original_values['name'] != form.cleaned_data['name']:
                changes.append(f"name: {self._original_values['name']} → {form.cleaned_data['name']}")
            if self._original_values['is_active'] != form.cleaned_data['is_active']:
                changes.append(f"active: {self._original_values['is_active']} → {form.cleaned_data['is_active']}")
        
        message = (
            f"Updated location <strong>{location.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name}<br>"
            f"<small class='text-muted'>"
            f"Changes: {', '.join(changes) if changes else 'No changes'}"
            f"</small>"
        )
        
        self.request.toast_message = {
            'message': message,
            'type': 'warning',
        }
        
        return response

    def form_invalid(self, form):
        """Handle form validation errors by displaying them in the form"""
        return self.render_to_response(self.get_context_data(form=form))

class LocationDeleteView(LoginRequiredMixin, LocationAnnotationMixin, DeleteView):
    model = Location
    template_name = 'sensors/location_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        location = self.get_object()
        place = location.place
        success_url = self.get_success_url()
        
        message = (
            f"Deleted location <strong>{location.name}</strong> from "
            f"<i class='bi bi-house-gear'></i> {place.name}<br>"
            f"<small class='text-muted'>"
            f"Status: {'Active' if location.is_active else 'Inactive'}<br>"
            f"Devices: {location.devices.count()}"
            f"</small>"
        )
        
        location.delete()
        
        self.request.toast_message = {
            'message': message,
            'type': 'danger',
            'addToHistory': True
        }
        
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return reverse('sensors:place_detail', kwargs={'place_slug': self.object.place.slug})

# Device Views
class DeviceListView(LoginRequiredMixin, LocationAnnotationMixin, ListView):
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
        # Clear any stale toast messages for this view
        if hasattr(self.request, '_messages'):
            storage = messages.get_messages(self.request)
            # Iterate through messages to clear them
            for _ in storage:
                pass  # Simply iterating clears the storage
        
        # Add place to context
        place_slug = self.kwargs.get('place_slug')
        if place_slug:
            place = get_object_or_404(Place, slug=place_slug)
            context['place'] = place
            
            # Get location if specified
            location_pk = self.request.GET.get('location')
            if location_pk:
                context['location'] = get_object_or_404(Location, pk=location_pk, place=place)
            
            # Get all locations for the place with device counts
            context['locations'] = place.locations.annotate(
                active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
                inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
            ).select_related('place')
            
        return context

class DeviceDetailView(LoginRequiredMixin, LocationAnnotationMixin, DetailView):
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

class DeviceCreateView(LoginRequiredMixin, LocationAnnotationMixin, CreateView):
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
        kwargs['place'] = self.place
        kwargs['initial_location'] = self.location
        
        # Add debug logging
        # ic("DeviceCreateView - get_form_kwargs:", {
        #     'place': kwargs['place'].name if kwargs.get('place') else None,
        #     'initial_location': kwargs.get('initial_location'),
        #     'has_data': bool(kwargs.get('data')),
        # })
        
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

    def form_valid(self, form):
        response = super().form_valid(form)
        device = self.object
        location = device.location
        place = location.place
        
        message = (
            f"Created device <strong>{device.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {device.device_type or '-'}<br>"
            f"Model: {device.model or '-'}<br>"
            f"Status: {'Active' if device.is_active else 'Inactive'}"
            f"</small>"
        )
        
        self.request.toast_message = {
            'message': message,
            'type': 'success',
            'addToHistory': True
        }
        
        return response

class DeviceMoveLocationView(LoginRequiredMixin, View):
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

@method_decorator(csrf_protect, name='dispatch')
@login_required
@csrf_protect
def siteplan_update(request, place_slug):
    try:
        device.objects.filter(location__place=place, is_active=True).count()
        devices_inactive = Device.objects.filter(location__place=place, is_active=False).count()
        sensors_active = Sensor.objects.filter(device__location__place=place, is_active=True).count()
        sensors_inactive = Sensor.objects.filter(device__location__place=place, is_active=False).count()
        
        # Get location statistics
        locations = place.locations.annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        ).values('id', 'name', 'is_active', 'active_devices_count', 'inactive_devices_count')
        
        return JsonResponse({
            'devices_active': devices_active,
            'devices_inactive': devices_inactive,
            'sensors_active': sensors_active,
            'sensors_inactive': sensors_inactive,
            'locations': list(locations)
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'message': 'Invalid JSON data',
            'type': 'danger',
            'tags': 'error layout-update'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'message': f'Error updating site plan: {str(e)}',
            'type': 'danger',
            'tags': 'error layout-update'
        }, status=500)

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

@method_decorator(csrf_protect, name='dispatch')
class ToastHistoryView(LoginRequiredMixin, View):
    def get(self, request):
        """Retrieve the toast history and mark as read."""
        # Get database history for current user
        notifications = ToastNotification.objects.filter(
            user=request.user
        ).order_by('-created_at')[:50]
        
        # Mark all as read
        notifications.update(read=True)
        
        # Convert to list for JSON response
        history = list(notifications.values('message', 'type', 'created_at'))
        
        return JsonResponse({
            'history': history
        })

    def delete(self, request):
        """Clear the toast history for the current user."""
        # Clear session history
        if 'toast_history' in request.session:
            del request.session['toast_history']
            request.session.modified = True
        
        # Clear database history for current user only
        ToastNotification.objects.filter(user=request.user).delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Toast history cleared successfully'
        })

class ToggleActiveView(View):
    """Consolidated view for toggling active status of locations, devices, and sensors."""
    
    def post(self, request: HttpRequest, place_slug: str, model: str, pk: int) -> JsonResponse:
        """Handle POST request to toggle active status.
        
        Args:
            request: The HTTP request
            place_slug: The slug of the place
            model: The type of model to toggle (location, device, or sensor)
            pk: The primary key of the model instance
        """
        try:
            # Validate model type
            if model not in ['location', 'device', 'sensor']:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Invalid model type: {model}'
                }, status=400)

            # Get request data
            data = json.loads(request.body)
            intended_state = data.get('is_active', False)
            
            # Get the place
            place = get_object_or_404(Place, slug=place_slug)
            
            # Get and validate the object based on model type
            if model == 'location':
                obj = get_object_or_404(Location, pk=pk, place=place)
            elif model == 'device':
                obj = get_object_or_404(Device, pk=pk, location__place=place)
                # Check if trying to activate device with inactive location
                if intended_state and not obj.location.is_active:
                    return JsonResponse({
                        'status': 'warning',
                        'message': (
                            f"Cannot activate device <strong>{obj.name}</strong> because its location "
                            f"<strong>{obj.location.name}</strong> is inactive.<br>"
                            f"<small class='text-muted'>Please activate the location first.</small>"
                        ),
                        'is_active': False,
                        'type': 'warning',
                        'toast': {
                            'message': (
                                f"Cannot activate device <strong>{obj.name}</strong> because its location "
                                f"<strong>{obj.location.name}</strong> is inactive.<br>"
                                f"<small class='text-muted'>Please activate the location first.</small>"
                            ),
                            'type': 'warning',
                            'addToHistory': True
                        }
                    })
            elif model == 'sensor':
                obj = get_object_or_404(Sensor, pk=pk, device__location__place=place)
            
            # Store affected items before the change
            affected_items = []
            if model == 'location':
                affected_items = [
                    f"{device.name} ({len(device.sensors.all())} sensors)"
                    for device in obj.devices.all()
                ]
            elif model == 'device':
                affected_items = [sensor.name for sensor in obj.sensors.all()]

            # Update the active status
            obj.is_active = intended_state
            obj.save()
            
            # If deactivating, cascade the change
            if not intended_state:
                if model == 'location':
                    Device.objects.filter(location=obj).update(is_active=False)
                    Sensor.objects.filter(device__location=obj).update(is_active=False)
                elif model == 'device':
                    Sensor.objects.filter(device=obj).update(is_active=False)
            
            # Build status message
            message = self._build_status_message(obj, model, intended_state, affected_items)
            
            # Prepare response data
            # Determine message type based on state transition
            message_type = 'success' if intended_state else 'danger'  # success for activation, danger for deactivation
            
            response_data = {
                'status': 'success',
                'message': message,
                'is_active': obj.is_active,
                'type': message_type,
                'toast': {
                    'message': message,
                    'type': message_type,  # Use same type for toast
                    # 'addToHistory': True
                }
            }
            
            # # Build and add toast message
            # self.request.toast_message = {
            #     'message': message,
            #     'type': message_type,
            #     'addToHistory': True
            # }
            
            return JsonResponse(response_data)

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

    def _build_status_message(self, obj, model: str, is_active: bool, affected_items: list) -> str:
        """Build a descriptive status message with icons and affected items."""
        
        action = 'Activated' if is_active else 'Deactivated'
        
        if model == 'location':
            message = (
                f"{action} <i class='bi bi-geo-alt'></i> {obj.name} in "
                f"<i class='bi bi-house-gear'></i> {obj.place.name}"
            )
            if not is_active and affected_items:  # Only show affected items when deactivating
                message += "<br><br>Affected devices:<ul class='mb-0'>"
                for device in affected_items:
                    message += f"<li><i class='bi bi-hdd-rack'></i> {device}</li>"
                message += "</ul>"
                
        elif model == 'device':
            message = (
                f"{action} <i class='bi bi-hdd-rack'></i> {obj.name} in "
                f"<i class='bi bi-house-gear'></i> {obj.location.place.name} > "
                f"<i class='bi bi-geo-alt'></i> {obj.location.name}"
            )
            if not is_active and affected_items:  # Only show affected items when deactivating
                message += "<br><br>Affected sensors:<ul class='mb-0'>"
                for sensor in affected_items:
                    message += f"<li><i class='bi bi-thermometer'></i> {sensor}</li>"
                message += "</ul>"
                
        else:  # sensor
            message = (
                f"{action} <i class='bi bi-thermometer'></i> {obj.name} in "
                f"<i class='bi bi-house-gear'></i> {obj.device.location.place.name} > "
                f"<i class='bi bi-geo-alt'></i> {obj.device.location.name} > "
                f"<i class='bi bi-hdd-rack'></i> {obj.device.name}"
            )
            
        return message

class DeviceUpdateView(LoginRequiredMixin, LocationAnnotationMixin, UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['location'] = self.object.location
        context['device'] = self.object
        return context
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        kwargs['place'] = self.place
        kwargs['referrer'] = self.request.META.get('HTTP_REFERER', '')
        return kwargs

    def form_valid(self, form):
        # Store original values before save
        device = self.get_object()
        self._original_values = {
            'name': device.name,
            'is_active': device.is_active,
            'location': device.location,
            'device_type': device.device_type,
            'model': device.model
        }
        
        response = super().form_valid(form)
        device = self.object
        changes = []
        
        # Build list of changes
        if hasattr(self, '_original_values'):
            if self._original_values['name'] != form.cleaned_data['name']:
                changes.append(f"name: {self._original_values['name']} → {form.cleaned_data['name']}")
            if self._original_values['is_active'] != form.cleaned_data['is_active']:
                changes.append(f"active: {self._original_values['is_active']} → {form.cleaned_data['is_active']}")
            if self._original_values['location'] != form.cleaned_data['location']:
                changes.append(f"location: {self._original_values['location'].name} → {form.cleaned_data['location'].name}")
            if self._original_values['device_type'] != form.cleaned_data['device_type']:
                changes.append(f"type: {self._original_values['device_type']} → {form.cleaned_data['device_type']}")
            if self._original_values['model'] != form.cleaned_data['model']:
                changes.append(f"model: {self._original_values['model']} → {form.cleaned_data['model']}")

        # Build toast message
        message = (
            f"Updated device <strong>{device.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {device.location.place.name} > "
            f"<i class='bi bi-geo-alt'></i> {device.location.name}<br>"
            f"<small class='text-muted'>"
            f"Changes: {', '.join(changes) if changes else 'No changes'}"
            f"</small>"
        )
        
        self.request.toast_message = {
            'message': message,
            'type': 'warning',
            'addToHistory': True
        }
        
        return response

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.place.slug,
            'pk': self.object.pk
        })

class DeviceDeleteView(LoginRequiredMixin, LocationAnnotationMixin, DeleteView):
    model = Device
    template_name = 'sensors/device_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get place from the device's location
        context['place'] = self.object.location.place
        context['place_slug'] = self.object.location.place.slug
        return context

    def get_success_url(self):
        # Redirect to place detail page after deletion
        return reverse('sensors:place_detail', 
                      kwargs={'place_slug': self.object.location.place.slug})

class DeviceActiveSensorsView(LoginRequiredMixin, View):
    def get(self, request, place_slug, pk):
        device = get_object_or_404(Device, pk=pk)
        
        try:
            active_sensors = device.sensors.filter(is_active=True)
            
            sensors_data = [{
                'name': sensor.name,
                'type': sensor.sensor_type,
                'unit': sensor.unit,
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
            }, status=500)

class SensorCreateView(LoginRequiredMixin, LocationAnnotationMixin, CreateView):
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
        form.instance.sensor = self.sensor
        response = super().form_valid(form)
        success_message = self.get_success_message(form.cleaned_data)
        
        self.request.toast_message = {
            'message': success_message,
            'type': 'success',
            'addToHistory': True
        }
        
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
            f"<i class='bi bi-hdd-rack'></i> {device.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {sensor.sensor_type or '-'}<br>"
            f"Unit: {sensor.unit or '-'}<br>"
            f"Status: {'Active' if sensor.is_active else 'Inactive'}"
            f"</small>"
        )

    def get_success_url(self):
        return reverse('sensors:sensor_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class SensorListView(LoginRequiredMixin, LocationAnnotationMixin, ListView):
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

class SensorDetailView(LoginRequiredMixin, LocationAnnotationMixin, DetailView):
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
                    context['recent_readings'] = readings[:10]  # Last 10 readings
            except Exception as e:
                ic(f"Error getting sensor readings: {str(e)}")  # Keep this
                context['readings_error'] = str(e)
        
        return context

class SensorUpdateView(LoginRequiredMixin, LocationAnnotationMixin, UpdateView):
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
        
        self.request.toast_message = {
            'message': success_message,
            'type': 'warning',
            'addToHistory': True
        }
        
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

class SensorDeleteView(LoginRequiredMixin, DeleteView):
    model = Sensor
    template_name = 'sensors/sensor_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        sensor = self.get_object()
        device = sensor.device
        location = device.location
        place = location.place
        success_url = self.get_success_url()
        
        message = (
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
        
        self.request.toast_message = {
            'message': message,
            'type': 'danger',
            'addToHistory': True
        }
        
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.device.pk
        })

class SensorReadingListView(LoginRequiredMixin, ListView):
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

class SensorReadingDetailView(LoginRequiredMixin, DetailView):
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

class SensorReadingCreateView(LoginRequiredMixin, LocationAnnotationMixin, CreateView):
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
        
        self.request.toast_message = {
            'message': success_message,
            'type': 'success',
            'addToHistory': True
        }
        
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

@login_required
@csrf_protect
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

def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    # Get place from kwargs or from the device's location
    if 'place_slug' in self.kwargs:
        context['place'] = self.get_place()
    else:
        # Get place from the device being deleted
        context['place'] = self.object.location.place
    
    # Ensure place_slug is available for URL reversals
    context['place_slug'] = context['place'].slug
    return context