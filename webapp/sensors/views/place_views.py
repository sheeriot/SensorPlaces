# Django Stuff
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.utils.safestring import mark_safe
# from typing import Dict, Any, Optional, cast

# App stuff
from ..models import Place, Location, Device, Sensor, ToastNotification
from .place_forms import PlaceForm, PlaceDeleteForm
from ..map_fun import place_map_create
from .mixins import PlaceAnnotationMixin

# utility
import json
from decimal import Decimal

from icecream import ic

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
            # ic("Error creating place map:", str(e))
            context['place_map_html'] = ""
        
        return context

class PlaceDetailView(LoginRequiredMixin, PlaceAnnotationMixin, DetailView):
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
        
        # Add place_map_html to the context
        try:
            map_html = place_map_create(places=[self.object])
            context['place_map_html'] = map_html
        except Exception as e:
            context['place_map_html'] = ""
            
        return context

class PlaceCreateView(LoginRequiredMixin, CreateView):
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Create inactive help text to be used in form and toast messages
        self._inactive_help_text = mark_safe(
            '<i class="bi bi-exclamation-triangle me-2"></i>'
            'This place is inactive. All locations and devices within it will not collect data.'
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['inactive_help_text'] = self._inactive_help_text
        return kwargs

    def form_valid(self, form: PlaceForm):
        # First save the form to get the object
        self.object = form.save()
        place = self.object
        
        message = (
            f"Created place <strong>{place.name}</strong><br>"
            f"<small class='text-muted'>"
            f"Location: ({place.latitude}, {place.longitude})<br>"
            f"Status: {'Active' if place.is_active else 'inactive'}"
            f"</small>"
        )
        
        # Add inactive warning to message if place is inactive
        if not place.is_active:
            message += f"<br><small class='text-warning'>{self._inactive_help_text}</small>"
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        # ic("Toast: PlaceCreateView:", getattr(self.request, 'toast_message', None))
        
        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return reverse('sensors:place_detail', kwargs={'place_slug': self.object.slug})

class PlaceUpdateView(LoginRequiredMixin, UpdateView):
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'
    slug_url_kwarg = 'place_slug'
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Create inactive help text to be used in form and toast messages
        self._inactive_help_text = mark_safe(
            '<i class="bi bi-exclamation-triangle me-2"></i>'
            'This place is inactive. All locations and devices within it will not collect data.'
        )
        

    def get_initial(self):
        initial = super().get_initial()
        # Set the referrer in initial data
        initial['referrer'] = self.request.META.get('HTTP_REFERER', '')
        return initial
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['inactive_help_text'] = self._inactive_help_text
        return kwargs

    def form_valid(self, form: PlaceForm):
        # Get the object before saving to compare values
        place = self.get_object()
        original_values = {
            'name': place.name,
            'is_active': place.is_active,
            'latitude': place.latitude,
            'longitude': place.longitude,
            'siteplan_image': place.siteplan_image.name if place.siteplan_image else None
        }
        
        # Save the form
        self.object = form.save()
        
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
        
        # Add inactive warning to message if place is inactive
        if not form.cleaned_data['is_active']:
            message += f"<br><small class='text-warning'>{self._inactive_help_text}</small>"
        
        # Set toast message directly on request instead of session
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        # ic("PlaceUpdateView setting toast_message:", {
        #     'message': message,
        #     'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        # })
        
        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        # Use cleaned_data from the form instead of request.POST
        if self.object and hasattr(self.object, 'referrer') and self.object.referrer:
            return self.object.referrer
        # Or check form's cleaned_data
        elif hasattr(self, 'form') and 'referrer' in self.form.cleaned_data and self.form.cleaned_data['referrer']:
            return self.form.cleaned_data['referrer']
        # Fallback to default URL
        return reverse('sensors:place_list')

class PlaceDeleteView(LoginRequiredMixin, DeleteView):
    model = Place
    template_name = 'sensors/place_confirm_delete.html'
    success_url = reverse_lazy('sensors:place_list')
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'
    form_class = PlaceDeleteForm
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = super().get_form_kwargs()
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        place = self.object
        
        # Get the form with the object instance properly set
        form_class = self.get_form_class()
        form = form_class(request.POST, instance=place)
        
        if form.is_valid():
            # Store place data before deletion
            place_data = {
                'name': place.name,
                'latitude': place.latitude,
                'longitude': place.longitude,
                'is_active': place.is_active
            }
            
            message = (
                f"Deleted place <strong>{place_data['name']}</strong> "
                f"<small class='text-muted'>{place_data['latitude']:.6f}, {place_data['longitude']:.6f}</small>"
            )
            
            # Get count of active locations before deletion
            active_locations = Location.objects.filter(
                place=place,
                is_active=True
            ).annotate(
                active_devices=Count('devices', filter=Q(devices__is_active=True))
            )
            
            if active_locations.exists():
                message += "<br>Affected active locations:<ul class='mb-0'>"
                for loc in active_locations:
                    message += f"<li>{loc.name} ({loc.active_devices} active devices)</li>"
                message += "</ul>"
            
            message += "</small>"
            
            # Before we delete the place, add a toast notification without place association
            # Setting the place association for a Place deletion would create a foreign key issue
            # because the Place would be deleted before the notification could be saved
            setattr(request, 'toast_message', {
                'message': message,
                'type': 'warning'
            })
            
            # Delete the place
            success_url = self.get_success_url()
            self.object.delete()
            
            return HttpResponseRedirect(success_url)
        else:
            return self.form_invalid(form)

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

from django import forms

class LocationPositionForm(forms.Form):
    id = forms.IntegerField()
    x_pos = forms.DecimalField(max_digits=5, decimal_places=2)
    y_pos = forms.DecimalField(max_digits=5, decimal_places=2)

    def clean_x_pos(self):
        x_pos = self.cleaned_data['x_pos']
        return Decimal(str(round(float(x_pos), 2)))

    def clean_y_pos(self):
        y_pos = self.cleaned_data['y_pos']
        return Decimal(str(round(float(y_pos), 2)))

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
        
        # Validate and update each location's position
        for loc_data in changed_locations:
            # Validate the data using the form
            form = LocationPositionForm(loc_data)
            if not form.is_valid():
                return JsonResponse({
                    'message': f"Invalid position data: {form.errors}",
                    'type': 'danger'
                }, status=400)
            
            location = get_object_or_404(Location, id=form.cleaned_data['id'], place=place)
            old_x = float(location.x_pos)
            old_y = float(location.y_pos)
            new_x = float(form.cleaned_data['x_pos'])
            new_y = float(form.cleaned_data['y_pos'])
            
            # Only process if position actually changed
            if abs(old_x - new_x) > 0.01 or abs(old_y - new_y) > 0.01:
                # Update position with cleaned (rounded) values
                location.x_pos = form.cleaned_data['x_pos']
                location.y_pos = form.cleaned_data['y_pos']
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
