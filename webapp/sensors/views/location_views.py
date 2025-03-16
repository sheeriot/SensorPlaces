from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet

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
        # ic(kwargs)
        self.place = self.get_place()
        self.locations = self.get_annotated_locations(self.place)

    def get_success_url(self):
        return reverse('sensors:location_detail', kwargs={'place_slug': self.kwargs.get('place_slug'), 'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self.place
        kwargs['locations'] = self.locations
        
        # Set initial data properly
        kwargs['initial'] = kwargs.get('initial', {})
        kwargs['initial'].update({
            'is_active': self.place.is_active,
            'place': self.place.pk,  # Use the primary key, not the object
            'referrer': self.request.GET.get('next', '')
        })
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        context['place'] = self.place
        context['locations'] = self.locations
        
        # Add a fallback cancel URL
        if self.object and self.object.pk:
            context['cancel_fallback_url'] = reverse('sensors:location_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.object.pk
            })
        else:
            context['cancel_fallback_url'] = reverse('sensors:place_detail', kwargs={
                'place_slug': self.place.slug
            })
        
        return context

    def form_valid(self, form):
        # Explicitly set the place on the form instance
        form.instance.place = self.place
        response = super().form_valid(form)
        ic(vars(form.instance))
        message = (
            f"Created location <strong>{self.object.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {self.place.name}<br>"
            f"<small class='text-muted'>"
            f"Status: {'Active' if self.object.is_active else 'inactive'}"
            f"</small>"
        )
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        return response
    
    def form_invalid(self, form):
        """Override form_invalid to debug form errors"""
        ic("Form is invalid, errors:", form.errors)
        ic("Form data:", form.data)
        
        # Try to manually create the object to see if it works
        try:
            location = Location(
                name=form.instance.name,
                place_id=form.instance.place_id,
                is_active=form.instance.is_active,
                x_pos=form.instance.x_pos,
                y_pos=form.instance.y_pos
            )
            location.save()
            ic("Manually created location:", location)
            
            # Redirect to the success URL
            return HttpResponseRedirect(self.get_success_url())
        except Exception as e:
            ic("Error creating location manually:", str(e))
        
        return super().form_invalid(form)

    def post(self, request, *args, **kwargs):
        """Override post to debug form validation"""
        form = self.get_form()
        ic("LocationCreateView.post - checking form validity")
        if form.is_valid():
            ic("Form is valid, calling form_valid")
            return self.form_valid(form)
        else:
            ic("Form is invalid, errors:", form.errors)
            ic("Form data:", form.data)
            ic("Form instance:", vars(form.instance))
            ic("Form fields:", form.fields)
            return self.form_invalid(form)

class LocationUpdateView(LoginRequiredMixin, PlaceAnnotationMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # ic(kwargs)
        self.place = self.get_place()
        self.locations = self.get_annotated_locations(self.place)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self.place
        kwargs['locations'] = self.locations
        if self.object and self.object.is_active:
            # Get active devices for this location
            kwargs['devices_active'] = self.object.devices.filter(is_active=True).annotate(
                sensor_count=Count('sensors', filter=Q(sensors__is_active=True))
            )
        if self.place and not kwargs.get('instance'):
            kwargs['initial'] = kwargs.get('initial', {})
            kwargs['initial']['place'] = self.place
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
        place = get_object_or_404(Place, slug=self.kwargs.get('place_slug'))
        form.instance.place = place
        response = super().form_valid(form)
        location = self.object
        
        # Track original values
        original_values = {
            'name': location.name,
            'is_active': location.is_active,
        }
        
        # Build changes list
        changes = []
        if original_values['name'] != form.cleaned_data['name']:
            changes.append(f"Name: {original_values['name']} → {form.cleaned_data['name']}")
        if original_values['is_active'] != form.cleaned_data['is_active']:
            changes.append(f"Status: {'active' if original_values['is_active'] else 'inactive'} → {'active' if form.cleaned_data['is_active'] else 'inactive'}")

        # Build toast message
        message = (
            f"Updated location <strong>{location.name}</strong> in "
            f"<i class='bi bi-house-gear'></i> {place.name}<br>"
            f"<small class='text-muted'>"
            f"Changes: {', '.join(changes) if changes else 'No changes'}"
            f"</small>"
        )
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        })
        
        # Store the toast message in session for redirect
        self.request.session['pending_toast'] = self.request.toast_message
        
        return response

    def get_success_url(self):
        return reverse('sensors:location_detail', kwargs={
            'place_slug': self.kwargs['place_slug'],
            'pk': self.object.pk
        })

class LocationDeleteView(LoginRequiredMixin, PlaceAnnotationMixin, DeleteView):
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
        
        # ic("LocationDeleteView setting toast_message:", {
        #     'message': message,
        #     'type': 'danger'
        # })
        
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        # Use stored place_slug for redirect
        return reverse('sensors:place_detail', 
                      kwargs={'place_slug': self.place_slug})
