from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from .models import Place, Location, Device, Sensor, SensorReading
from .utils import get_sensor_readings  #, write_sensor_reading
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
from icecream import ic
import logging
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)

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

class PlaceDetailView(LocationAnnotationMixin, DetailView):
    model = Place
    context_object_name = 'place'
    template_name = 'sensors/place_detail.html'
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'

    def get_queryset(self) -> QuerySet[Place]:
        return Place.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from icecream import ic
        import json
        
        # Ensure place is in context
        if 'place' not in context and hasattr(self, 'object'):
            context['place'] = self.object
            
        # Debug locations from LocationAnnotationMixin
        if 'locations' in context:
            locations_data = []
            for location in context['locations']:
                locations_data.append({
                    'id': location.id,
                    'name': location.name,
                    'x': location.x_coord_value,  # Match JavaScript property names
                    'y': location.y_coord_value,  # Match JavaScript property names
                    'is_active': location.is_active,
                    'active_devices_count': location.active_devices_count
                })
            context['locations_json'] = json.dumps(locations_data)
            
            ic("Locations in context:", locations_data)
            ic("Locations count:", len(locations_data))
            ic("First location data:", locations_data[0] if locations_data else None)
        else:
            ic("No locations in context!")
            context['locations_json'] = '[]'
            
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
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'
    slug_url_kwarg = 'place_slug'
    success_message = "Place updated successfully."

    def setup(self, request, *args, **kwargs):
        """Store original values when the view is initialized"""
        super().setup(request, *args, **kwargs)
        self._original_values = {}
        if hasattr(self, 'object'):
            # Get the object if not already loaded
            obj = self.get_object() if not self.object else self.object
            self._original_values = {
                'site_plan': obj.site_plan.name if obj.site_plan else None,
                'is_active': obj.is_active,
                # Add other fields you want to track
            }

    def form_invalid(self, form):
        return super().form_invalid(form)

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
            return response
        except Exception as e:
            raise

    def get_success_message(self, cleaned_data):
        place = self.object
        messages = []

        # Now we can safely compare the values
        if self._original_values.get('site_plan') != (place.site_plan.name if place.site_plan else None):
            if place.site_plan:
                messages.append("Site plan was updated")
            else:
                messages.append("Site plan was removed")

        if not messages:
            messages.append("Place updated successfully")

        return " | ".join(messages)

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
    form_class = PlaceDeleteForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self.get_object()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
        place = self.get_object()
        
        # Get locations with device counts for the warning message
        context['locations'] = Location.objects.filter(place=place).annotate(
            active_devices_count=Count('devices', filter=Q(devices__is_active=True)),
            inactive_devices_count=Count('devices', filter=Q(devices__is_active=False))
        ).order_by('name')
        
        context['place'] = place
        return context

    def form_invalid(self, form):
        """Handle form validation errors with regular form messages"""
        return self.render_to_response(self.get_context_data(form=form))

    def delete(self, request, *args, **kwargs):
        """Only add toast notification after successful deletion"""
        place = self.get_object()
        success_url = self.get_success_url()
        message_type = 'danger'
        
        # Create success message
        success_message = (
            f"Deleted place <strong>{place.name}</strong><br>"
            f"<small class='text-muted'>"
            f"Location: ({place.latitude}, {place.longitude})<br>"
            f"Status: {'Active' if place.is_active else 'Inactive'}"
            f"</small>"
        )
        
        # Delete the place
        place.delete()
        
        # Only add toast notification after successful deletion
        if hasattr(request, 'session'):
            toast_history = request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': message_type,
                'timestamp': timezone.now().isoformat()
            })
            request.session['toast_history'] = toast_history
            request.session.modified = True
            
        return HttpResponseRedirect(success_url)

    def form_valid(self, form):
        """Validate form before deletion"""
        return self.delete(self.request)

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
        
        return context

class LocationCreateView(SuccessMessageMixin, LocationAnnotationMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Cache the place
        self.place = get_object_or_404(Place, slug=self.kwargs.get('place_slug'))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Add place to initial data
        kwargs['initial'] = kwargs.get('initial', {})
        kwargs['initial']['place'] = self.place
        
        # Add referrer to form kwargs
        referrer = self.request.META.get('HTTP_REFERER')
        if referrer:
            kwargs['initial']['referrer'] = referrer
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        context['place'] = self.place
        context['place_url'] = reverse('sensors:place_detail', kwargs={'place_slug': self.place.slug})
        context['locations'] = self.place.locations.annotate(
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
        default_url = reverse('sensors:place_locations', kwargs={'place_slug': self.object.place.slug})
        return default_url

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

    def get_success_url(self):
        return reverse('sensors:place_locations', kwargs={'place_slug': self.object.place.slug})

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
    try:
        place = get_object_or_404(Place, slug=place_slug)
        data = json.loads(request.body)
        
        # Track changes with before/after values
        changes = []
        
        # Site plan transform changes
        if 'site_plan_scale' in data:
            old_scale = place.site_plan_scale
            new_scale = float(data['site_plan_scale'])
            if old_scale != new_scale:
                changes.append(
                    f"Scale: {old_scale:.2f} → {new_scale:.2f}"
                )
                place.site_plan_scale = new_scale
        
        if 'site_plan_x' in data:
            old_x = place.site_plan_x
            new_x = float(data['site_plan_x'])
            if old_x != new_x:
                changes.append(
                    f"X offset: {old_x:.1f}px → {new_x:.1f}px"
                )
                place.site_plan_x = new_x
        
        if 'site_plan_y' in data:
            old_y = place.site_plan_y
            new_y = float(data['site_plan_y'])
            if old_y != new_y:
                changes.append(
                    f"Y offset: {old_y:.1f}px → {new_y:.1f}px"
                )
                place.site_plan_y = new_y

        if changes:
            place.save(update_fields=['site_plan_scale', 'site_plan_x', 'site_plan_y'])
        
        # Location position changes
        location_changes = []
        for update in data.get('locations', []):
            location_id = update.get('id')
            new_x = update.get('x')
            new_y = update.get('y')
            
            if location_id and new_x is not None and new_y is not None:
                location = Location.objects.filter(id=location_id, place=place).first()
                if location:
                    old_x = float(location.x_coord) if location.x_coord is not None else 0
                    old_y = float(location.y_coord) if location.y_coord is not None else 0
                    new_x = float(new_x)
                    new_y = float(new_y)
                    
                    if old_x != new_x or old_y != new_y:
                        location_changes.append({
                            'name': location.name,
                            'changes': f"({old_x:.1f}, {old_y:.1f}) → ({new_x:.1f}, {new_y:.1f})"
                        })
                        location.x_coord = new_x
                        location.y_coord = new_y
                        location.save(update_fields=['x_coord', 'y_coord'])

        # Construct detailed message
        message_parts = [f"Updated site plan layout for <strong>{place.name}</strong>"]
        
        if changes:
            message_parts.append("<br><small class='text-muted'>Site Plan Changes:")
            changes_with_icon = [f"<i class='bi bi-house-gear'></i> {change}" for change in changes]
            message_parts.append(", ".join(changes_with_icon))
            message_parts.append("</small>")
        
        if location_changes:
            message_parts.append("<br><small class='text-muted'>Location Changes:")
            for change in location_changes:
                message_parts.append(
                    f"<br><i class='bi bi-geo-alt'></i> {change['name']}: {change['changes']}"
                )
            message_parts.append("</small>")

        success_message = "".join(message_parts)
        
        # Add to session toast history
        toast_count = 0
        if hasattr(request, 'session'):
            toast_history = request.session.get('toast_history', [])
            toast_history.append({
                'message': success_message,
                'type': 'warning',  # Using warning type for updates
                'timestamp': timezone.now().isoformat(),
                'tags': 'warning safe layout-update'  # Add tags for filtering
            })
            request.session['toast_history'] = toast_history
            request.session.modified = True
            toast_count = len(toast_history)

        # Add to Django messages if available (persistent storage)
        messages.warning(request, success_message, extra_tags='safe layout-update')
        
        response_data = {
            'status': 'success',
            'message': success_message,
            'type': 'warning',
            'tags': 'warning safe layout-update',
            'toast_count': toast_count,  # Add count to response
            'changes': {
                'site_plan': {
                    'scale': place.site_plan_scale,
                    'x': place.site_plan_x,
                    'y': place.site_plan_y
                },
                'locations': location_changes
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        error_message = f'Error updating layout: {str(e)}'
        
        # Add error to session toast history
        if hasattr(request, 'session'):
            toast_history = request.session.get('toast_history', [])
            toast_history.append({
                'message': error_message,
                'type': 'danger',
                'timestamp': timezone.now().isoformat(),
                'tags': 'error layout-update'
            })
            request.session['toast_history'] = toast_history
            request.session.modified = True

        # Add to Django messages
        messages.error(request, error_message, extra_tags='layout-update')
        
        return JsonResponse({
            'error': str(e),
            'type': 'danger',
            'tags': 'error layout-update',
            'message': error_message
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
                    'addToHistory': True
                }
            }
            
            print(f"[ToggleActive] Response: {json.dumps(response_data, indent=2)}")
            
            return JsonResponse(response_data)

        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            print(f"[ToggleActive] Error: {str(e)}")
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
        
        # Delete the device
        device.delete()
        
        # Add success message to session
        messages.success(request, success_message)
        
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return reverse('sensors:place_devices', kwargs={'place_slug': self.object.location.place.slug})

class DeviceActiveSensorsView(View):
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
                )
            )
            
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
    context['places'] = Place.objects.all()
    return context