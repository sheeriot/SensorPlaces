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

    def get_success_url(self):
        return reverse('sensors:location_detail', kwargs={'place_slug': self.kwargs.get('place_slug'), 'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self.get_place()
        # ic(kwargs['place'])
        kwargs['initial'] = kwargs.get('initial', {})
        kwargs['initial'].update({
            'is_active': kwargs['place'].is_active,  # Set initial is_active to match place
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
        
        # ic("LocationCreateView setting toast_message:", {
        #     'message': message,
        #     'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        # })
        
        return response

class LocationUpdateView(LoginRequiredMixin, PlaceAnnotationMixin, UpdateView):
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
