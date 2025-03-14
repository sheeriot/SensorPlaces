from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.http import HttpResponseRedirect

from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet, Prefetch

from ..models import Place, Location, Device, Sensor
from ..forms import DeviceForm
from .mixins import PlaceAnnotationMixin

from icecream import ic

# Device Views
class DeviceListView(LoginRequiredMixin, PlaceAnnotationMixin, ListView):
    model = Device
    context_object_name = 'devices'
    template_name = 'sensors/device_list.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.place = self.get_place()
        location_pk = self.kwargs.get('location_pk', None)
        if location_pk:
            self.location = get_object_or_404(Location, pk=location_pk, place=self.place)
        self.locations = self.get_annotated_locations(self.place)

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
        ic('device_list_context', context)

        # Add place to context
        place = self.get_place()
        context['place'] = place
        
        # Get location if specified
        location_pk = self.request.GET.get('location', None)
        if location_pk:
            context['location'] = get_object_or_404(Location, pk=location_pk, place=place)
            
        context['locations'] = self.get_annotated_locations(place)
        return context

class DeviceDetailView(LoginRequiredMixin, PlaceAnnotationMixin, DetailView):
    model = Device
    context_object_name = 'device'
    template_name = 'sensors/device_detail.html'
    object: Device

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

class DeviceCreateView(LoginRequiredMixin, PlaceAnnotationMixin, CreateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'
    object: Device

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.place = self.get_place()
        location_pk = self.kwargs.get('location_pk', None)
        if location_pk:
            self.location = get_object_or_404(Location, pk=location_pk, place=self.place)
        self.locations = self.get_annotated_locations(self.place)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self.place
        kwargs['locations'] = self.locations
        kwargs['initial'] = {
            'location': self.location,
            'referrer': self.request.GET.get('next')
        }
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['place'] = self.place
        if self.location:
            context['location'] = self.location
        context['locations'] = self.locations
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
        
        # ic("DeviceCreateView setting toast_message:", {
        #     'message': message,
        #     'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        # })
        
        return response

class DeviceUpdateView(LoginRequiredMixin, PlaceAnnotationMixin, UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.place = self.get_place()

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.place.slug,
            'pk': self.object.pk
        })

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self.place
        kwargs['locations'] = self.get_annotated_locations(self.place)
        kwargs['initial'] = {
            'referrer': self.request.META.get('HTTP_REFERER')
        }
        return kwargs

    def form_valid(self, form):
        # Store original values before save
        device = self.get_object()
        self._original_values = {
            'name': device.name,
            'is_active': device.is_active,
            'location': device.location,
            'device_type': device.device_type,
            'model': device.model,
            'serial_number': device.serial_number
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
            if self._original_values['serial_number'] != form.cleaned_data['serial_number']:
                changes.append(f"serial number: {self._original_values['serial_number']} → {form.cleaned_data['serial_number']}")

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
        # ic("DeviceUpdateView toast message:", {
        #     'message': message,
        #     'type': 'success' if form.cleaned_data['is_active'] else 'warning',
        #     'place': device.location.place
        # })
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning',
            'place': self.place
        })
        ic("added toast_message to request")
        return response

class DeviceDeleteView(LoginRequiredMixin, PlaceAnnotationMixin, DeleteView):
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
                      kwargs={'place_slug': self.place.slug})

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