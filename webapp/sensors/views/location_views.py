from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.utils.safestring import mark_safe

from ..models import Place, Location, Device, Sensor
from ..forms import LocationForm
from .mixins import PlaceAnnotationMixin

import json
from decimal import Decimal
from icecream import ic

# Location Views
class LocationListView(LoginRequiredMixin, PlaceAnnotationMixin, ListView):
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

class LocationDetailView(LoginRequiredMixin, PlaceAnnotationMixin, DetailView):
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

class LocationCreateView(LoginRequiredMixin, PlaceAnnotationMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'
    object: Location

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place and locations
        self._place = self.get_place()
        self._locations = self.get_annotated_locations(self._place)
        
        # Create inactive help text to be used in form and toast messages
        if self._place and not self._place.is_active:
            self._inactive_help_text = mark_safe(
                '<div class="form-text text-warning-emphasis mt-2">'
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                f'This location will be inactive because Place "{self._place.name}" is inactive. '
                f'All devices within it will not collect data.'
                '</div>'
            )
        else:
            self._inactive_help_text = None

    def get_success_url(self):
        return reverse('sensors:location_detail', kwargs={
            'place_slug': self.kwargs.get('place_slug'), 
            'pk': self.object.pk
        })

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self._place
        kwargs['locations'] = self._locations
        kwargs['inactive_help_text'] = self._inactive_help_text
        
        # Set initial data properly
        kwargs['initial'] = kwargs.get('initial', {})
        kwargs['initial'].update({
            'is_active': self._place.is_active,
            'place': self._place.pk,  # Use the primary key, not the object
            'referrer': self.request.GET.get('next', '')
        })
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        context['place'] = self._place
        context['locations'] = self._locations
        
        # Add a fallback cancel URL
        if self.object and self.object.pk:
            context['cancel_fallback_url'] = reverse('sensors:location_detail', kwargs={
                'place_slug': self._place.slug,
                'pk': self.object.pk
            })
        else:
            context['cancel_fallback_url'] = reverse('sensors:place_detail', kwargs={
                'place_slug': self._place.slug
            })
        
        return context

    def form_valid(self, form):
        # Explicitly set the place on the form instance
        form.instance.place = self._place
        # Save the form to get the object
        self.object = form.save()
        
        message = (
            f"Created location <strong>{self.object.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {self._place.name}<br>"
            f"<small class='text-muted'>"
            f"Status: {'Active' if self.object.is_active else 'inactive'}"
            f"</small>"
        )
        
        # Add inactive warning to message if location is inactive
        if not self.object.is_active and self._inactive_help_text:
            message += f"<br><small class='text-warning'>{self._inactive_help_text}</small>"
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)

    def post(self, request, *args, **kwargs):
        """Override post to debug form validation"""
        form = self.get_form()

        if form.is_valid():
            # ic("Form is valid, calling form_valid")
            return self.form_valid(form)
        else:
            # ic("Form is invalid, errors:", form.errors)
            # ic("Form data:", form.data)
            # ic("Form instance:", vars(form.instance))
            # ic("Form fields:", form.fields)
            return self.form_invalid(form)

class LocationUpdateView(LoginRequiredMixin, PlaceAnnotationMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place and locations
        self._place = self.get_place()
        self._locations = self.get_annotated_locations(self._place)
        
        # Default inactive_help_text to None
        self._inactive_help_text = None
        self._devices_active = []
        
        try:
            # Try to get the location if we're updating
            location = self.get_object()
            
            # If place is inactive, create help text about that
            if self._place and not self._place.is_active:
                # Check if location is active when it shouldn't be
                if location and location.is_active:
                    # Get the list of affected devices before fixing
                    self._devices_active = list(location.devices.filter(is_active=True).annotate(
                        sensor_count=Count('sensors', filter=Q(sensors__is_active=True))
                    ).prefetch_related('sensors'))
                    
                    # Fix the inconsistency - set location to inactive
                    location.is_active = False
                    location.save()
                    
                    # Just log the inconsistency with ic
                    ic(f"Fixed inconsistency: Location {location.id} ({location.name}) was active "
                       f"but its Place {self._place.id} ({self._place.name}) is inactive.")
                    ic(f"Affected devices: {len(self._devices_active)}")
                
                # Standard message for inactive place
                self._inactive_help_text = mark_safe(
                    '<div class="form-text text-warning-emphasis mt-2">'
                    '<i class="bi bi-exclamation-triangle me-2"></i>'
                    f'This location will be inactive because Place "{self._place.name}" is inactive. '
                    f'All devices within it will not collect data.'
                    '</div>'
                )
            # If location is active, check for active devices
            elif location and location.is_active:
                # Get active devices with sensor counts
                self._devices_active = list(location.devices.filter(is_active=True).annotate(
                    sensor_count=Count('sensors', filter=Q(sensors__is_active=True))
                ).prefetch_related('sensors'))
                
                active_device_count = len(self._devices_active)
                
                if active_device_count > 0:
                    # Generate the list of active devices with their sensor counts
                    active_devices_list = ''.join([
                        f'<li><i class="bi bi-hdd-rack text-muted me-1"></i>{device.name} '
                        f'<small class="text-muted">({device.sensor_count} active sensors)</small></li>'
                        for device in self._devices_active
                    ])
                    
                    self._inactive_help_text = mark_safe(
                        '<div class="form-text text-warning-emphasis mt-2">'
                        f'<i class="bi bi-exclamation-triangle me-2"></i>'
                        f'This location has {active_device_count} active device{"s" if active_device_count > 1 else ""}:'
                        f'<ul class="list-unstyled mb-0 mt-1 ms-4">{active_devices_list}</ul>'
                        '</div>'
                    )
        except Exception as e:
            # If we can't get the object yet (e.g., in a GET request before the object exists)
            ic(f"Error in LocationUpdateView.setup: {str(e)}")

    def get_initial(self):
        initial = super().get_initial()
        # Set the referrer in initial data
        initial['referrer'] = self.request.META.get('HTTP_REFERER', '')
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self._place
        kwargs['locations'] = self._locations
        kwargs['inactive_help_text'] = self._inactive_help_text
        
        # Get active devices for this location if it's active
        location = self.get_object()
        if location and location.is_active:
            kwargs['devices_active'] = location.devices.filter(is_active=True).annotate(
                sensor_count=Count('sensors', filter=Q(sensors__is_active=True))
            )
            
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        context['place'] = self._place
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
        # Explicitly set the place on the form instance
        form.instance.place = self._place
        
        # Get the object before saving to compare values
        location = self.get_object()
        original_values = {
            'name': location.name,
            'is_active': location.is_active,
        }
        
        # Save the form
        self.object = form.save()
        
        # Build changes list
        changes = []
        if original_values['name'] != form.cleaned_data['name']:
            changes.append(f"Name: {original_values['name']} → {form.cleaned_data['name']}")
        if original_values['is_active'] != form.cleaned_data['is_active']:
            changes.append(f"Status: {'active' if original_values['is_active'] else 'inactive'} → {'active' if form.cleaned_data['is_active'] else 'inactive'}")

        # Build toast message
        message = (
            f"Updated location <strong>{self.object.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {self._place.name}<br>"
            f"<small class='text-muted'>"
            f"Changes: {', '.join(changes) if changes else 'No changes'}"
            f"</small>"
        )
        
        # Add inactive warning to message if location is inactive
        if not self.object.is_active and self._inactive_help_text:
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
        # Use cleaned_data from the form instead of request.POST
        if self.object and hasattr(self.object, 'referrer') and self.object.referrer:
            return self.object.referrer
        # Or check form's cleaned_data
        elif hasattr(self, 'form') and 'referrer' in self.form.cleaned_data and self.form.cleaned_data['referrer']:
            return self.form.cleaned_data['referrer']
        # Fallback to default URL
        return reverse('sensors:location_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class LocationDeleteView(LoginRequiredMixin, PlaceAnnotationMixin, DeleteView):
    model = Location
    template_name = 'sensors/location_confirm_delete.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place
        self._place = self.get_place()
        
        # Create inactive help text to be used in form and toast messages
        if self._place and not self._place.is_active:
            self._inactive_help_text = mark_safe(
                '<div class="form-text text-warning-emphasis mt-2">'
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                f'This location is inactive because Place "{self._place.name}" is inactive.'
                '</div>'
            )
        else:
            self._inactive_help_text = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        context['place'] = self._place
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        location = self.object
        # Store place_slug before deletion for redirect
        self.place_slug = self._place.slug
        
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
            f"<i class='bi bi-house-gear'></i> {self._place.name}<br>"
            f"<small class='text-muted'>"
            f"Status: {'Active' if location.is_active else 'inactive'}"
        )
        
        if devices_info:
            message += f"<br>Affected devices:<br>{'; '.join(devices_info)}"
        
        message += "</small>"
        
        # Add inactive warning to message if location is inactive
        if not location.is_active and self._inactive_help_text:
            message += f"<br><small class='text-warning'>{self._inactive_help_text}</small>"
        
        # Delete the location
        location.delete()
        
        # Set toast message directly on request for middleware
        setattr(request, 'toast_message', {
            'message': message,
            'type': 'danger'
        })
        
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        # Use stored place_slug for redirect
        return reverse('sensors:place_detail', 
                      kwargs={'place_slug': self.place_slug})
