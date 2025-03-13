from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet, Prefetch
from django.core.exceptions import PermissionDenied

from ..models import Place, Location, Device, Sensor
from ..forms import DeviceForm
from .mixins import LocationAnnotationMixin

import json
# from icecream import ic

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

# class DeviceMoveLocationView(LoginRequiredMixin, View):

#     def post(self, request, pk):
#         # Get the device and validate it exists
#         device = get_object_or_404(Device, pk=pk)
        
#         try:
#             data = json.loads(request.body)
#             new_location_id = data.get('new_location_id')
#             # 'new_location_id', new_location_id)
#             if not new_location_id:
#                 return JsonResponse({'error': 'new_location_id is required'}, status=400)
            
#             # Get the new location and validate it exists
#             new_location = get_object_or_404(Location, pk=new_location_id)
#             # 'new_location', new_location)
#             # Store old location for counter updates
#             old_location = device.location
            
#             # Validate that the new location is active
#             if not new_location.is_active:
#                 return JsonResponse(
#                     {'error': 'Cannot move device to inactive location'}, 
#                     status=400
#                 )
            
#             # Validate that the new location belongs to the same place
#             if new_location.place != device.location.place:
#                 return JsonResponse(
#                     {'error': 'Cannot move device to a different place'}, 
#                     status=400
#                 )
            
#             # Update the device's location
#             device.location = new_location
#             device.save()
#             # 'saved device.location', device.location)
#             # Get updated counts
#             old_location_count = old_location.devices.filter(is_active=True).count()
#             new_location_count = new_location.devices.filter(is_active=True).count()
#             results = JsonResponse({
#                 'success': True,
#                 'new_location_name': new_location.name,
#                 'old_location_count': old_location_count,
#                 'new_location_count': new_location_count,
#                 'devices_active_count': Device.objects.filter(
#                     location__place=device.location.place,
#                     is_active=True
#                 ).count()
#             })
#             return results
            
#         except json.JSONDecodeError:
#             return JsonResponse({'error': 'Invalid JSON'}, status=400)
#         except Exception as e:
#             return JsonResponse({'error': str(e)}, status=500)