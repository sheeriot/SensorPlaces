from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from .models import Place, Location, Device, Sensor, SensorReading, ToastNotification, ToastReadStatus
from .utils import get_sensor_readings  #, add_toast_message
from .forms import SensorForm, PlaceForm, DeviceForm, LocationForm, PlaceDeleteForm
from .map_fun import place_map_create
# from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponseRedirect
from django.views.decorators.http import require_POST
# from django.contrib.admin.views.decorators import staff_member_required
from typing import Any, Dict, List, Optional, Type
from django.db.models.query import QuerySet
from django.db.models import Count, Q, Exists, OuterRef
from django.db.models.functions import Lower
from django.db.models import F, Subquery
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
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
# from .utils import mark_toast_as_read, clear_toast_history

# Add the mixin first, before any classes that use it
class LocationAnnotationMixin:
    """Mixin to add annotated locations to context data."""
    
    kwargs: dict
    
    def get_place(self) -> Place:
        """Get the place object from the URL kwargs.
        
        Returns:
            Place: The place object for this view
            
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
    
    def get_location_data(self, location: Location) -> dict:
        """Convert a Location instance to a JSON-serializable dictionary.
        
        Args:
            location: The Location model instance
            
        Returns:
            Dict containing the location data for JavaScript
        """
        return {
            'id': str(location.pk),
            'name': str(location.name),
            'x_pos': float(location.x_pos) if isinstance(location.x_pos, Decimal) else location.x_pos,
            'y_pos': float(location.y_pos) if isinstance(location.y_pos, Decimal) else location.y_pos,
            'is_active': bool(location.is_active),
            'devices_active_count': getattr(location, 'devices_active_count', 0)
        }

    def get_annotated_locations(self, place: Place) -> QuerySet[Location]:
        """Get annotated locations for a place.
        
        Args:
            place: The Place model instance
            
        Returns:
            QuerySet of Location instances with annotations
        """
        return Location.objects.filter(place=place).annotate(
            devices_active_count=Count(
                'devices',
                filter=Q(devices__is_active=True),
                distinct=True
            ),
            devices_inactive_count=Count(
                'devices',
                filter=Q(devices__is_active=False),
                distinct=True
            ),
            sensors_active_count=Count(
                'devices__sensors',
                filter=Q(devices__sensors__is_active=True),
                distinct=True
            ),
            sensors_inactive_count=Count(
                'devices__sensors',
                filter=Q(devices__sensors__is_active=False),
                distinct=True
            )
        ).order_by('-is_active', Lower('name'))

    def get_context_data(self, **kwargs) -> dict:
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
        
        # Add place statistics using distinct counts
        context.update({
            'locations': locations,  # Full queryset for template
            'locations_json': json.dumps(locations_data),  # JSON for JavaScript
            'devices_active': Device.objects.filter(
                location__place=place, 
                is_active=True
            ).distinct().count(),
            'devices_inactive': Device.objects.filter(
                location__place=place, 
                is_active=False
            ).distinct().count(),
            'sensors_active': Sensor.objects.filter(
                device__location__place=place, 
                is_active=True
            ).distinct().count(),
            'sensors_inactive': Sensor.objects.filter(
                device__location__place=place, 
                is_active=False
            ).distinct().count(),
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
                devices_active_count=Count('locations__devices', filter=Q(locations__devices__is_active=True)),
                active_sensors_count=Count('locations__devices__sensors', filter=Q(locations__devices__sensors__is_active=True))
            ).order_by('-is_active', Lower('name'))
        return self._queryset

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
        try:
            map_html = place_map_create(places=self.get_queryset())
            context['place_map_html'] = map_html
        except Exception as e:
            ic("Error creating place map:", str(e))
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

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
        return context

class PlaceCreateView(LoginRequiredMixin, CreateView):
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'

    def form_valid(self, form: PlaceForm) -> HttpResponseRedirect:
        response = super().form_valid(form)
        place: Place = self.object
        
        message = (
            f"Created place <strong>{place.name}</strong><br>"
            f"<small class='text-muted'>"
            f"Location: ({place.latitude}, {place.longitude})<br>"
            f"Status: {'Active' if place.is_active else 'inactive'}"
            f"</small>"
        )
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        ic("PlaceCreateView setting toast_message:", {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        return response

    def get_success_url(self) -> str:
        return reverse('sensors:place_detail', kwargs={'place_slug': self.object.slug})

class PlaceUpdateView(LoginRequiredMixin, UpdateView):
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'
    slug_url_kwarg = 'place_slug'

    def get_initial(self) -> dict:
        initial = super().get_initial()
        initial['referrer'] = self.request.META.get('HTTP_REFERER', '')
        return initial

    def form_valid(self, form: PlaceForm) -> HttpResponseRedirect:
        place: Place = self.get_object()
        original_values = {
            'name': place.name,
            'is_active': place.is_active,
            'latitude': place.latitude,
            'longitude': place.longitude,
            'siteplan_image': place.siteplan_image.name if place.siteplan_image else None
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
        
        # Set toast message directly on request instead of session
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        ic("PlaceUpdateView setting toast_message:", {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        return response

    def get_success_url(self) -> str:
        if 'referrer' in self.request.POST:
            return self.request.POST['referrer']
        return reverse('sensors:place_list')

class PlaceDeleteView(LoginRequiredMixin, DeleteView):
    model = Place
    template_name = 'sensors/place_confirm_delete.html'
    success_url = reverse_lazy('sensors:place_list')
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'
    form_class = PlaceDeleteForm

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        place = self.object
        success_url = self.get_success_url()
        
        # Get active locations and devices before deletion
        active_locations = Location.objects.filter(
            place=place,
            is_active=True
        ).annotate(
            active_devices=Count('devices', filter=Q(devices__is_active=True))
        )
        
        message = (
            f"Deleted place <strong>{place.name}</strong><br>"
            f"<small class='text-muted'>"
            f"Location: ({place.latitude}, {place.longitude})<br>"
            f"Status: {'Active' if place.is_active else 'inactive'}"
        )
        
        if active_locations.exists():
            message += "<br>Affected active locations:<ul class='mb-0'>"
            for loc in active_locations:
                message += f"<li>{loc.name} ({loc.active_devices} active devices)</li>"
            message += "</ul>"
        
        message += "</small>"
        
        # Set toast message directly on request for middleware
        setattr(request, 'toast_message', {
            'message': message,
            'type': 'danger'
        })
        
        ic("PlaceDeleteView setting toast_message:", {
            'message': message,
            'type': 'danger'
        })
        
        place.delete()
        
        return HttpResponseRedirect(success_url)

@login_required
@csrf_protect
def place_stats(request, place_slug):
    """Get statistics for a place."""
    try:
        # Get the place
        place = get_object_or_404(Place, slug=place_slug)
        
        # Get location statistics
        locations = Location.objects.filter(place=place).annotate(
            devices_active_count=Count('devices', filter=Q(devices__is_active=True)),
            devices_inactive_count=Count('devices', filter=Q(devices__is_active=False)),
            sensors_active_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=True)),
            sensors_inactive_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=False))
        ).values(
            'id', 'name', 'is_active',
            'devices_active_count', 'devices_inactive_count',
            'sensors_active_count', 'sensors_inactive_count'
        )
        
        # Get device statistics
        devices = Device.objects.filter(location__place=place).annotate(
            sensors_active_count=Count('sensors', filter=Q(sensors__is_active=True)),
            sensors_inactive_count=Count('sensors', filter=Q(sensors__is_active=False))
        ).values(
            'id', 'name', 'is_active', 'location_id',
            'sensors_active_count', 'sensors_inactive_count'
        )
        
        # Get sensor statistics
        sensors = Sensor.objects.filter(device__location__place=place).values(
            'id', 'name', 'is_active', 'device_id',
            'sensor_type', 'data_type', 'unit'
        )
        
        # Get unread toast count
        unread_count = ToastNotification.get_unread_count(
            user=request.user,
            place=place
        )
        
        return JsonResponse({
            'success': True,
            'stats': {
                'locations': list(locations),
                'devices': list(devices),
                'sensors': list(sensors),
                'unread_toast_count': unread_count,
                'total': {
                    'locations': {
                        'active': sum(1 for loc in locations if loc['is_active']),
                                     'inactive': sum(1 for loc in locations if not loc['is_active'])
                    },
                    'devices': {
                        'active': sum(1 for dev in devices if dev['is_active']),
                        'inactive': sum(1 for dev in devices if not dev['is_active'])
                    },
                    'sensors': {
                        'active': sum(1 for sen in sensors if sen['is_active']),
                        'inactive': sum(1 for sen in sensors if not sen['is_active'])
                    }
                }
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@csrf_protect
def siteplan_update(request, place_slug):
    try:
        # Get the place
        place = get_object_or_404(Place, slug=place_slug)
        
        # Parse the incoming JSON data
        data = json.loads(request.body)
        changed_locations = data.get('locations', [])
        
        if not changed_locations:
            return JsonResponse({
                'message': 'No changes to save',
                'type': 'info'
            })
        
        # Track changes for message
        location_changes = []
        
        # Update each location's position
        for loc_data in changed_locations:
            location = get_object_or_404(Location, id=loc_data['id'], place=place)
            old_x = float(location.x_pos)
            old_y = float(location.y_pos)
            new_x = float(loc_data['x_pos'])
            new_y = float(loc_data['y_pos'])
            
            # Only process if position actually changed
            if abs(old_x - new_x) > 0.01 or abs(old_y - new_y) > 0.01:  # Small threshold for float comparison
                # Update position
                location.x_pos = new_x
                location.y_pos = new_y
                location.save()
                
                # Add to changes list with ID
                location_changes.append({
                    'id': location.id,
                    'name': location.name,
                    'old_pos': {'x': old_x, 'y': old_y},
                    'new_pos': {'x': new_x, 'y': new_y}
                })

        # If no actual changes were made, return early
        if not location_changes:
            return JsonResponse({
                'message': 'No position changes detected',
                'type': 'info'
            })

        # Build detailed message
        message = (
            f"Updated site plan for <strong><i class='bi bi-house-gear'></i> {place.name}</strong><br>"
            f"<small class='text-muted'>Changed locations:<ul class='mb-0'>"
        )
        
        for change in location_changes:
            message += (
                f"<li><i class='bi bi-geo-alt'></i> {change['name']}<br>"
                f"Position: ({change['old_pos']['x']:.1f}, {change['old_pos']['y']:.1f}) → "
                f"({change['new_pos']['x']:.1f}, {change['new_pos']['y']:.1f})</li>"
            )
        
        message += "</ul></small>"
        
        # Get updated statistics
        devices_active = Device.objects.filter(location__place=place, is_active=True).count()
        devices_inactive = Device.objects.filter(location__place=place, is_active=False).count()
        sensors_active = Sensor.objects.filter(device__location__place=place, is_active=True).count()
        sensors_inactive = Sensor.objects.filter(device__location__place=place, is_active=False).count()
        
        # Get updated location statistics
        locations = place.locations.annotate(
            devices_active_count=Count('devices', filter=Q(devices__is_active=True)),
            devices_inactive_count=Count('devices', filter=Q(devices__is_active=False))
        ).values('id', 'name', 'is_active', 'devices_active_count', 'devices_inactive_count')
        
        return JsonResponse({
            'message': message,
            'type': 'warning',
            'changes': {
                'locations': [
                    {
                        'id': change['id'],
                        'name': change['name'],
                        'new_position': {
                            'x_pos': change['new_pos']['x'],
                            'y_pos': change['new_pos']['y']
                        }
                    } for change in location_changes
                ]
            },
            'devices_active': devices_active,
            'devices_inactive': devices_inactive,
            'sensors_active': sensors_active,
            'sensors_inactive': sensors_inactive,
            'locations': list(locations)
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'message': (
                f"Invalid data received while updating site plan for "
                f"<i class='bi bi-house-gear'></i> {place_slug}"
            ),
            'type': 'danger',
            'tags': 'error layout-update'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'message': (
                f"Error updating site plan for "
                f"<i class='bi bi-house-gear'></i> {place.name if 'place' in locals() else place_slug}<br>"
                f"<small class='text-muted'>{str(e)}</small>"
            ),
            'type': 'danger',
            'tags': 'error layout-update'
        }, status=500)

# Location Views
class LocationListView(LoginRequiredMixin, LocationAnnotationMixin, ListView):
    model = Location
    context_object_name = 'locations'
    template_name = 'sensors/location_list.html'

    def get_queryset(self) -> QuerySet[Location]:
        if not hasattr(self, '_queryset'):
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            self._queryset = self.get_annotated_locations(place)
        return self._queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        place = context['place']

        # Add place statistics
        context.update({
            'place_devices_active': Device.objects.filter(location__place=place, is_active=True).count(),
            'place_devices_inactive': Device.objects.filter(location__place=place, is_active=False).count(),
            'place_sensors_active': Sensor.objects.filter(device__location__place=place, is_active=True).count(),
            'place_sensors_inactive': Sensor.objects.filter(device__location__place=place, is_active=False).count(),
        })
        
        return context

class LocationDetailView(LoginRequiredMixin, LocationAnnotationMixin, DetailView):
    model = Location
    context_object_name = 'location'
    template_name = 'sensors/location_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        
        # Use the annotated location data from the mixin
        location = self.get_annotated_locations(self.object.place).get(pk=self.object.pk)
        context['location'] = location

        # Add annotated devices to context
        context['devices'] = Device.objects.filter(
            location=self.object
        ).select_related(
            'device_type'
        ).prefetch_related(
            'sensors'
        ).annotate(
            sensors_active_count=Count('sensors', filter=Q(sensors__is_active=True), distinct=True),
            sensors_inactive_count=Count('sensors', filter=Q(sensors__is_active=False), distinct=True)
        ).order_by(
            '-is_active', 
            Lower('name')
        )
        
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
        kwargs['initial'].update({
            'place': place,
            'is_active': place.is_active,  # Set initial is_active to match place
            'referrer': self.request.GET.get('next', '')
        })
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
            f"Status: {'Active' if location.is_active else 'inactive'}"
            f"</small>"
        )
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        ic("LocationCreateView setting toast_message:", {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        return response

class LocationUpdateView(LoginRequiredMixin, LocationAnnotationMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.object and self.object.is_active:
            # Get active devices for this location
            devices = self.object.devices.filter(is_active=True).annotate(
                sensor_count=Count('sensors', filter=Q(sensors__is_active=True))
            )
            
            # Format devices for the form
            devices_active = [{
                'name': device.name,
                'count_label': f'{device.sensor_count} active sensors'
            } for device in devices]
            
            if devices_active:
                kwargs['initial'] = kwargs.get('initial', {})
                kwargs['initial']['devices_active'] = devices_active
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        location = self.get_object()
        
        # Add all devices to context with annotations
        context['devices'] = Device.objects.filter(
            location=location
        ).select_related(
            'device_type'
        ).prefetch_related(
            'sensors'
        ).annotate(
            sensors_active_count=Count('sensors', filter=Q(sensors__is_active=True), distinct=True),
            sensors_inactive_count=Count('sensors', filter=Q(sensors__is_active=False), distinct=True)
        ).order_by(
            '-is_active', 
            Lower('name')
        )
        
        return context

    def form_valid(self, form):
        # Store original values before save
        location = self.get_object()
        original_values = {
            'name': location.name,
            'is_active': location.is_active
        }
        
        response = super().form_valid(form)
        location = self.object
        place = location.place
        changes = []
        
        # Build list of changes
        if location.name != original_values['name']:
            changes.append(f"name: {original_values['name']} → {location.name}")
        if location.is_active != original_values['is_active']:
            changes.append(f"status: {'Active' if original_values['is_active'] else 'inactive'} → {'Active' if location.is_active else 'inactive'}")

        message = f"Updated location <strong>{location.name}</strong> in <i class='bi bi-house-gear'></i> {place.name}"
        if changes:
            message += f"<br><small class='text-muted'>{'; '.join(changes)}</small>"
        
        # Store toast message in request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if location.is_active else 'warning'
        })
        
        ic("LocationUpdateView setting toast_message:", {
            'message': message,
            'type': 'success' if location.is_active else 'warning',
            'place_slug': self.kwargs.get('place_slug')
        })
        
        return response

    def get_success_url(self):
        return reverse('sensors:location_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class LocationDeleteView(LoginRequiredMixin, LocationAnnotationMixin, DeleteView):
    model = Location
    template_name = 'sensors/location_confirm_delete.html'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        location = self.object
        place = location.place
        # Store place_slug before deletion for redirect
        self.place_slug = place.slug
        
        # Get active devices info before deletion
        active_devices = Device.objects.filter(
            location=location,
            is_active=True
        ).annotate(
            sensor_count=Count('sensors', filter=Q(sensors__is_active=True))
        )
        
        devices_info = [f"{device.name} ({device.sensor_count} active sensors)" 
                       for device in active_devices]
        
        message = (
            f"Deleted location <strong>{location.name}</strong> from "
            f"<i class='bi bi-house-gear'></i> {place.name}<br>"
            f"<small class='text-muted'>"
            f"Status: {'Active' if location.is_active else 'inactive'}"
        )
        
        if devices_info:
            message += f"<br>Affected devices:<br>{'; '.join(devices_info)}"
        
        message += "</small>"
        
        # Delete the location
        location.delete()
        
        # Set toast message directly on request for middleware
        setattr(request, 'toast_message', {
            'message': message,
            'type': 'danger'
        })
        
        ic("LocationDeleteView setting toast_message:", {
            'message': message,
            'type': 'danger'
        })
        
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        # Use stored place_slug for redirect
        return reverse('sensors:place_detail', 
                      kwargs={'place_slug': self.place_slug})

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
                devices_active_count=Count('devices', filter=Q(devices__is_active=True)),
                devices_inactive_count=Count('devices', filter=Q(devices__is_active=False))
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
                self._location = get_object_or_404(
                    Location,
                    pk=location_pk,
                    place=self.place
                )
        return self._location

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        device_pk = self.kwargs.get('device_pk')
        if device_pk:
            device = get_object_or_404(Device, pk=device_pk, location__place=self.place)
            if not device.is_active:
                form.fields['is_active'].help_text = f"<i class='bi bi-hdd-rack'></i> {device.name} is inactive"
        return form

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self.place
        
        # Set initial data including location and is_active
        initial = kwargs.get('initial', {})
        
        # If we have a location, use it for initial data
        if self.location:
            initial['location'] = self.location
            # Set is_active based on location's status
            initial['is_active'] = self.location.is_active
        
        kwargs['initial'] = initial
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['place'] = self.place
        
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
            f"Status: {'Active' if device.is_active else 'inactive'}"
            f"</small>"
        )
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        ic("DeviceCreateView setting toast_message:", {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        return response

class DeviceUpdateView(LoginRequiredMixin, LocationAnnotationMixin, UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'

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
        
        # Add debug logging
        ic("DeviceUpdateView toast message:", {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning',
            'place': device.location.place
        })
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning',
            'place': device.location.place
        })
        
        return response

class DeviceDeleteView(LoginRequiredMixin, LocationAnnotationMixin, DeleteView):
    model = Device
    template_name = 'sensors/device_confirm_delete.html'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        device = self.object
        location = device.location
        place = location.place
        success_url = self.get_success_url()
        
        # Get active sensors before deletion
        active_sensors = device.sensors.filter(is_active=True)
        sensors_info = [sensor.name for sensor in active_sensors]
        
        message = (
            f"Deleted device <strong>{device.name}</strong> from "
            f"<i class='bi bi-house-gear'></i> {place.name} > "
            f"<i class='bi bi-geo-alt'></i> {location.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {device.device_type or '-'}<br>"
            f"Model: {device.model or '-'}<br>"
            f"Status: {'Active' if device.is_active else 'inactive'}"
        )
        
        # Add affected sensors section if there were any active sensors
        if sensors_info:
            message += "<br>Affected sensors:<ul class='mb-0'>"
            for sensor in sensors_info:
                message += f"<li><i class='bi bi-thermometer'></i> {sensor}</li>"
            message += "</ul>"
        
        message += "</small>"
        
        # Delete the device
        device.delete()
        
        # Set toast message directly on request for middleware
        setattr(request, 'toast_message', {
            'message': message,
            'type': 'danger'
        })
        
        ic("DeviceDeleteView setting toast_message:", {
            'message': message,
            'type': 'danger'
        })
        
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return reverse('sensors:place_detail', 
                      kwargs={'place_slug': self.object.location.place.slug})

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
                'devices_active_count': Device.objects.filter(
                    location__place=device.location.place,
                    is_active=True
                ).count()
            })
            return results
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

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

class SensorCreateView(LoginRequiredMixin, LocationAnnotationMixin, CreateView):
    model = Sensor
    form_class = SensorForm
    template_name = 'sensors/sensor_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        device_pk = self.kwargs.get('device_pk')
        if device_pk:
            device = get_object_or_404(Device, pk=device_pk, location__place=self.get_place())
            kwargs['device'] = device
            kwargs['initial'] = {
                'is_active': device.is_active,
                'device_active': device.is_active  # Pass device active status to form
            }
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'sensor'
        context['place'] = self.get_place()
        
        device_pk = self.kwargs.get('device_pk')
        if device_pk:
            device = get_object_or_404(Device, pk=device_pk, location__place=self.get_place())
            context['device'] = device
            context['location'] = device.location
        
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
        
        ic("SensorCreateView setting toast_message:", {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        return response

    def get_success_url(self):
        return reverse('sensors:sensor_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class SensorUpdateView(LoginRequiredMixin, LocationAnnotationMixin, UpdateView):
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
        
        ic("SensorUpdateView setting toast_message:", {
            'message': message,
            'type': 'success' if sensor.is_active else 'warning',
            'place_slug': self.kwargs.get('place_slug')
        })
        
        return response

    def get_success_url(self):
        return reverse('sensors:sensor_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class SensorDeleteView(LoginRequiredMixin, LocationAnnotationMixin, DeleteView):
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

class SensorReadingListView(LoginRequiredMixin, LocationAnnotationMixin, ListView):
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

class SensorReadingDetailView(LoginRequiredMixin, LocationAnnotationMixin, DetailView):
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
        
        ic("SensorReadingCreateView setting toast_message:", {
            'message': message,
            'type': 'success'
        })
        
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

@method_decorator(csrf_protect, name='dispatch')
class ToastAPIView(LoginRequiredMixin, View):
    """Single API endpoint for all toast-related operations."""
    
    def get(self, request, place_slug):
        """Handle GET requests for toast messages.
        
        Query Parameters:
            show_all: bool - If True, return all messages, if False only unread
        """
        try:
            place = get_object_or_404(Place, slug=place_slug)
            show_all = request.GET.get('show_all', 'false').lower() == 'true'
            
            # Base query with read status annotation
            notifications = ToastNotification.objects.filter(
                user=request.user,
                place=place
            ).annotate(
                read=Exists(
                    ToastReadStatus.objects.filter(
                        user=request.user,
                        toast_id=OuterRef('pk')
                    )
                )
            )
            
            # Filter unread if not showing all
            if not show_all:
                notifications = notifications.filter(
                    ~Exists(ToastReadStatus.objects.filter(
                        user=request.user,
                        toast_id=OuterRef('pk')
                    ))
                )
            
            # Get the last 50 notifications
            history = notifications.order_by('-created_at')[:50].values(
                'id',
                'message',
                'type',
                'created_at',
                'read'
            )
            
            return JsonResponse({
                'success': True,
                'history': list(history),
                'unread_count': ToastNotification.get_unread_count(
                    user=request.user,
                    place=place
                )
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    def post(self, request, place_slug):
        """Handle POST requests for marking messages as read.
        
        POST Data:
            action: str - 'mark_read'
            toast_ids: int or list[int] - Single ID or list of IDs to mark as read
        """
        try:
            place = get_object_or_404(Place, slug=place_slug)
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'mark_read':
                toast_ids = data.get('toast_ids')
                if not toast_ids:
                    return JsonResponse({
                        'success': False,
                        'error': 'toast_ids is required'
                    }, status=400)
                
                # Convert single ID to list
                if isinstance(toast_ids, int):
                    toast_ids = [toast_ids]
                
                # Verify all toasts belong to this place and user
                toasts = ToastNotification.objects.filter(
                    id__in=toast_ids,
                    user=request.user,
                    place=place
                )
                
                if len(toasts) != len(toast_ids):
                    raise PermissionDenied("Some toast messages don't belong to this place or user")
                
                # Mark toasts as read
                for toast in toasts:
                    ToastReadStatus.objects.get_or_create(
                        user=request.user,
                        toast=toast
                    )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Marked {len(toasts)} messages as read',
                    'unread_count': ToastNotification.get_unread_count(
                        user=request.user,
                        place=place
                    )
                })
            
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Unknown action: {action}'
                }, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON'
            }, status=400)
        except PermissionDenied as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=403)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

@method_decorator(csrf_protect, name='dispatch')
class ToggleActiveView(LoginRequiredMixin, View):
    def post(self, request, place_slug):
        try:
            data = json.loads(request.body)
            model_type = data.get('model_type')
            object_id = data.get('id')

            if not model_type or not object_id:
                return JsonResponse({
                    'success': False,
                    'error': 'model_type and id are required'
                }, status=400)

            # Map model types to actual models
            model_map = {
                'place': Place,
                'location': Location,
                'device': Device,
                'sensor': Sensor
            }

            model_class = model_map.get(model_type.lower())
            if not model_class:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid model type: {model_type}'
                }, status=400)

            # Get the object and validate ownership through place
            obj = get_object_or_404(model_class, pk=object_id)

            # Get the place based on model type
            if model_type == 'place':
                place = obj
            elif model_type == 'location':
                place = obj.place
            elif model_type == 'device':
                place = obj.location.place
            else:  # sensor
                place = obj.device.location.place

            # Verify place matches URL
            if place.slug != place_slug:
                return JsonResponse({
                    'success': False,
                    'error': 'Object does not belong to this place'
                }, status=403)

            # Toggle the active status
            obj.is_active = not obj.is_active
            obj.save()

            # Build success message
            if model_type == 'place':
                name_path = f"{obj.name}"
            elif model_type == 'location':
                name_path = f"{place.name} > {obj.name}"
            elif model_type == 'device':
                name_path = f"{place.name} > {obj.location.name} > {obj.name}"
            else:  # sensor
                name_path = f"{place.name} > {obj.device.location.name} > {obj.device.name} > {obj.name}"

            # Set toast message using our standard pattern
            request.toast_message = {
                'message': (
                    f"{'Activated' if obj.is_active else 'Deactivated'} {model_type}: "
                    f"<strong>{name_path}</strong>"
                ),
                'type': 'success' if obj.is_active else 'warning'
            }

            # Ensure the JSON response includes the toast data
            response_data = {
                'success': True,
                'is_active': obj.is_active,
                'toast': {
                    'message': request.toast_message['message'],
                    'type': request.toast_message['type']
                }
            }

            return JsonResponse(response_data)

        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
