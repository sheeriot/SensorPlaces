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
from django import forms
from django.db import transaction
from django.shortcuts import render
from django.utils.decorators import method_decorator
# from typing import Dict, Any, Optional, cast

# App stuff
from ..models import Place, Location, Device, Sensor, ToastNotification, InfluxSource
from .place_forms import PlaceForm, PlaceDeleteForm
from ..map_fun import place_map_create
from .mixins import PlaceAnnotationMixin
from .views_fun import get_place_data, get_place_counts, get_annotated_locations, get_annotated_places, get_live_counts_context
from ..decorators import log_execution_time

# utility
import json
from decimal import Decimal

# Place Views
class PlaceListView(LoginRequiredMixin, ListView):
    model = Place
    context_object_name = 'places'
    template_name = 'sensors/place_list.html'
    
    def get_queryset(self) -> QuerySet[Place]:
        if not hasattr(self, '_queryset'):
            self._queryset = get_annotated_places()
        return self._queryset

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'place'
        try:
            map_html = place_map_create(places=self.get_queryset(), zoom_start=10)
            context['place_map_html'] = map_html
        except Exception as e:
            context['place_map_html'] = ""
        
        return context

@login_required
def siteplan_view(request, place_slug):
    place = get_object_or_404(Place, slug=place_slug)
    
    # Annotate locations with active/inactive device counts
    locations = Location.objects.filter(place=place).annotate(
        devices_active_count=Count('device', filter=Q(device__is_active=True)),
        devices_inactive_count=Count('device', filter=Q(device__is_active=False))
    )
    
    locations_json = json.dumps(
        [
            {
                "name": loc.name,
                "slug": loc.slug,
                "description": loc.description or "",
                "is_active": loc.is_active,
                "devices_active_count": loc.devices_active_count,
                "x_pos": float(loc.x_pos) if loc.x_pos is not None else None,
                "y_pos": float(loc.y_pos) if loc.y_pos is not None else None,
                "url": reverse('sensors:location_detail', args=[place.slug, loc.slug])
            }
            for loc in locations
        ]
    )
    
    return render(request, 'sensors/siteplan.html', {
        'place': place,
        'locations': locations, # Pass the queryset for the list card
        'locations_json': locations_json,
        'editable': True
    })

@method_decorator(log_execution_time, name='dispatch')
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
        
        # Add place data from get_place_data function.
        # This adds the correctly annotated 'locations' queryset, 'locations_json',
        # 'hide_inactive' state, and other counts to the context.
        place_data = get_place_data(self.object, self.request)
        context.update(place_data)

        # Add device and sensor counts to context for the live counts card
        context.update(get_live_counts_context(self.object))
        
        # Add InfluxDB sources to the context
        context['influxsources'] = InfluxSource.objects.filter(place=self.object)
        
        # Add place_map_html to the context
        try:
            map_html = place_map_create(places=[self.object])
            context['place_map_html'] = map_html
        except Exception as e:
            context['place_map_html'] = ""
            
        context['editable'] = True  # Enable the edit button on the siteplan
        
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
        
        # Cache the referrer for later use
        self._referrer = request.META.get('HTTP_REFERER', '')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['inactive_help_text'] = self._inactive_help_text
        
        # Set initial data with referrer
        kwargs['initial'] = kwargs.get('initial', {})
        kwargs['initial']['referrer'] = self._referrer
        kwargs['cancel_url'] = self.get_cancel_url()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.get_cancel_url()
        return context

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
        
        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return reverse('sensors:place_detail', kwargs={'place_slug': self.object.slug})

    def get_cancel_url(self):
        return reverse('sensors:place_list')

class PlaceUpdateView(LoginRequiredMixin, UpdateView):
    model = Place
    form_class = PlaceForm
    template_name = 'sensors/place_form.html'
    slug_url_kwarg = 'place_slug'
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Cache the place object early
        self._place = self.get_object()
        
        # Generate detailed inactive help text 
        self._inactive_help_text = self.get_place_inactive_help_text(self._place)
        
        # Cache the referrer for later use
        self._referrer = request.META.get('HTTP_REFERER', '')

    def get_place_inactive_help_text(self, place):
        """
        Generate help text for place inactive status.
        
        Args:
            place: The place object
            
        Returns:
            help_text: HTML string with warning message or None
        """
        if not place:
            return None
            
        # Basic message - short version
        basic_message = 'When inactive, all devices within this place will stop collecting data.'
        
        # Get active locations with device counts
        active_locations = Location.objects.filter(
            place=place,
            is_active=True
        ).annotate(
            active_devices=Count('devices', filter=Q(devices__is_active=True)),
            active_sensors=Count('devices__sensors', filter=Q(devices__sensors__is_active=True))
        ).order_by('name')
        
        active_location_count = active_locations.count()
        
        if active_location_count == 0:
            # Just return the basic message if no active locations
            return mark_safe(
                '<i class="bi bi-exclamation-triangle me-2"></i>' + basic_message
            )
            
        # Count total active devices and sensors
        total_active_devices = sum(loc.active_devices for loc in active_locations)
        total_active_sensors = sum(loc.active_sensors for loc in active_locations)
        
        # Generate a more concise list of active locations with their device and sensor counts
        active_locations_list = ''.join([
            f'<li>{loc.name} <span class="text-muted">({loc.active_devices} device{"s" if loc.active_devices != 1 else ""}, {loc.active_sensors} sensor{"s" if loc.active_sensors != 1 else ""})</span></li>'
            for loc in active_locations
        ])
        
        # Create concise help text
        help_text = mark_safe(
            f'<i class="bi bi-exclamation-triangle me-2"></i>{basic_message}<br>'
            f'<small><strong>Affected:</strong> {active_location_count} location{"s" if active_location_count > 1 else ""} '
            f'with {total_active_devices} device{"s" if total_active_devices != 1 else ""} '
            f'and {total_active_sensors} sensor{"s" if total_active_sensors != 1 else ""}</small>'
            f'<ul class="list-unstyled small mb-0 mt-1 ms-2">{active_locations_list}</ul>'
        )
            
        return help_text

    def get_initial(self):
        initial = super().get_initial()
        # Set the referrer in initial data
        initial['referrer'] = self._referrer
        return initial
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['inactive_help_text'] = self._inactive_help_text
        kwargs['cancel_url'] = self.get_cancel_url()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.get_cancel_url()
        return context

    def form_valid(self, form: PlaceForm):
        # Get the object before saving to compare values
        place = self._place
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
        
        # Add inactive warning to toast message if place is now inactive
        if not form.cleaned_data['is_active']:
            # Check if this is a change from active to inactive
            if original_values['is_active'] and not form.cleaned_data['is_active']:
                # Generate fresh inactive help text for the toast - but more concise version for the toast
                active_locations = Location.objects.filter(
                    place=self.object,
                    is_active=True
                ).annotate(
                    active_devices=Count('devices', filter=Q(devices__is_active=True)),
                    active_sensors=Count('devices__sensors', filter=Q(devices__sensors__is_active=True))
                )
                
                active_location_count = active_locations.count()
                if active_location_count > 0:
                    total_active_devices = sum(loc.active_devices for loc in active_locations)
                    total_active_sensors = sum(loc.active_sensors for loc in active_locations)
                    
                    message += (
                        f"<br><small class='text-warning'>"
                        f"<i class='bi bi-exclamation-triangle me-2'></i>Place set to inactive - "
                        f"{active_location_count} location{'s' if active_location_count != 1 else ''}, "
                        f"{total_active_devices} device{'s' if total_active_devices != 1 else ''}, and "
                        f"{total_active_sensors} sensor{'s' if total_active_sensors != 1 else ''} affected"
                        f"</small>"
                    )
                else:
                    message += (
                        f"<br><small class='text-warning'>"
                        f"<i class='bi bi-exclamation-triangle me-2'></i>Place set to inactive"
                        f"</small>"
                    )
            else:
                # This place was already inactive, just show a simple message
                message += (
                    f"<br><small class='text-warning'>"
                    f"<i class='bi bi-exclamation-triangle me-2'></i>Place is inactive"
                    f"</small>"
                )
        
        # Set toast message directly on request instead of session
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)

    def get_cancel_url(self):
        return reverse('sensors:place_detail', kwargs={'place_slug': self.object.slug})

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
    slug_url_kwarg = 'place_slug'
    slug_field = 'slug'

    def get_object(self, queryset=None):
        return get_object_or_404(Place, slug=self.kwargs['place_slug'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = self.object
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            context = self.get_context_data(object=self.object)
            html = render_to_string('sensors/place_confirm_delete_modal.html', context, request=request)
            return JsonResponse({'html': html})
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'redirect_url': self.get_success_url()})
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.request.POST.get('next', reverse_lazy('sensors:place_list'))

@login_required
def place_stats(request, place_slug):
    """Return device and sensor counts for a place."""
    place = get_object_or_404(Place, slug=place_slug)
    locations_active, locations_inactive, devices_active, devices_inactive, sensors_active, sensors_inactive = get_place_counts(place)
    
    context = {
        'locations_active': locations_active,
        'locations_inactive': locations_inactive,
        'devices_active': devices_active,
        'devices_inactive': devices_inactive,
        'sensors_active': sensors_active,
        'sensors_inactive': sensors_inactive
    }
    # ic(context) # This line was removed as per the edit hint
    return JsonResponse(context)


# Utility Forms
class LocationPositionForm(forms.Form):
    slug = forms.SlugField()
    x_pos = forms.DecimalField(max_digits=5, decimal_places=2)
    y_pos = forms.DecimalField(max_digits=5, decimal_places=2)

    def clean_x_pos(self):
        x_pos = self.cleaned_data['x_pos']
        return Decimal(str(round(float(x_pos), 2)))

    def clean_y_pos(self):
        y_pos = self.cleaned_data['y_pos']
        return Decimal(str(round(float(y_pos), 2)))

@csrf_protect
def siteplan_update(request, place_slug):
    """
    Handles AJAX requests to update the x, y positions of locations on a site plan.
    """
    if request.method != 'POST':
        return JsonResponse({'type': 'error', 'message': 'Invalid request method.'}, status=405)

    try:
        data = json.loads(request.body)
        locations_data = data.get('locations', [])
        place = get_object_or_404(Place, slug=place_slug)
        
        updated_locations_info = []
        
        with transaction.atomic():
            for loc_data in locations_data:
                form = LocationPositionForm(loc_data)
                if form.is_valid():
                    slug = form.cleaned_data['slug']
                    x_pos = form.cleaned_data['x_pos']
                    y_pos = form.cleaned_data['y_pos']
                    
                    try:
                        location = Location.objects.select_for_update().get(place=place, slug=slug)
                        
                        original_position = {'x_pos': location.x_pos, 'y_pos': location.y_pos}
                        
                        location.x_pos = x_pos
                        location.y_pos = y_pos
                        location.save(update_fields=['x_pos', 'y_pos'])
                        
                        updated_locations_info.append({
                            'slug': location.slug,
                            'name': location.name,
                            'original_position': {
                                'x_pos': float(original_position['x_pos']),
                                'y_pos': float(original_position['y_pos'])
                            },
                            'new_position': {
                                'x_pos': float(location.x_pos),
                                'y_pos': float(location.y_pos)
                            }
                        })
                        
                    except Location.DoesNotExist:
                        # This case is logged on the client-side, so just continue
                        continue
                else:
                    # Also logged on the client-side
                    continue

        if not updated_locations_info:
            return JsonResponse({
                'type': 'info',
                'message': 'No locations were updated.'
            })
            
        # Build a more detailed message
        changes_list = ''.join([
            f"<li>{info['name']}: position: ({info['original_position']['x_pos']}, {info['original_position']['y_pos']}) → ({info['new_position']['x_pos']}, {info['new_position']['y_pos']})</li>"
            for info in updated_locations_info
        ])
        
        message = mark_safe(
            f"Updated site plan for <strong>{place.name}</strong><br>"
            f"<small><ul class='list-unstyled mb-0'>{changes_list}</ul></small>"
        )
        
        # Add device/sensor counts for context
        counts = get_place_counts(place)
        
        return JsonResponse({
            'message': message,
            'type': 'warning',
            'changes': {'locations': updated_locations_info},
            **counts
        })

    except json.JSONDecodeError:
        return JsonResponse({'type': 'error', 'message': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'type': 'error', 'message': f'An unexpected error occurred: {e}'}, status=500)
