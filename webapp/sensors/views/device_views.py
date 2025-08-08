from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.http import HttpResponseRedirect

from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet, Prefetch
from django.utils.safestring import mark_safe

from ..models import Place, Location, Device, Sensor
from .device_forms import DeviceForm
from .mixins import PlaceAnnotationMixin
from .views_fun import get_place_counts, get_annotated_locations, get_live_counts_context
from icecream import ic

# Device Views
class DeviceListView(LoginRequiredMixin, PlaceAnnotationMixin, ListView):
    model = Location
    context_object_name = 'locations'
    template_name = 'sensors/device_list.html'

    def get_queryset(self) -> QuerySet[Location]:
        # Prefetch devices for each location
        devices_prefetch = Prefetch(
            'devices',
            queryset=Device.objects.annotate(
                sensors_active_count=Count('sensors', filter=Q(sensors__is_active=True)),
                sensors_inactive_count=Count('sensors', filter=Q(sensors__is_active=False))
            ).order_by('-is_active', 'name'),
            to_attr='devices_sorted'
        )

        qs = get_annotated_locations(self._place).prefetch_related(devices_prefetch)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        
        # Add hide_inactive state from GET param or cookie
        hide_inactive_param = self.request.GET.get('hide_inactive')
        if hide_inactive_param is not None:
            context['hide_inactive'] = hide_inactive_param.lower() == 'true'
        else:
            hide_inactive_cookie = self.request.COOKIES.get('hideInactive_device', 'false')
            context['hide_inactive'] = hide_inactive_cookie.lower() == 'true'
        
        # Add place to context
        place = self.get_place()
        context['place'] = place
        unassigned_devices = Device.objects.filter(location__place=place, location__slug='unassigned-devices').order_by('-is_active', 'name')
        context['unassigned_devices'] = unassigned_devices
        
        # Add live counts to context
        context.update(get_live_counts_context(place))

        # Get location if specified
        location_pk = self.request.GET.get('location', None)
        if location_pk:
            context['location'] = get_object_or_404(Location, pk=location_pk, place=place)
            
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
                .annotate(
                    active_sensors_count=Count('sensors', filter=Q(sensors__is_active=True)),
                    inactive_sensors_count=Count('sensors', filter=Q(sensors__is_active=False))
                ).prefetch_related(
                    Prefetch(
                        'sensors',
                        queryset=Sensor.objects.order_by('-is_active', Lower('name')),
                        to_attr='sensors_sorted'
                    ))
        return self._queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        device = self.object
        location = device.location
        
        context['model_name'] = 'device'
        context['place'] = self._place
        context['location'] = location
        context['sensors'] = device.sensors_sorted
        context['locations'] = get_annotated_locations(self._place)

        # Add hide_inactive state from GET param or cookie
        hide_inactive_param = self.request.GET.get('hide_inactive')
        if hide_inactive_param is not None:
            context['hide_inactive'] = hide_inactive_param.lower() == 'true'
        else:
            hide_inactive_cookie = self.request.COOKIES.get('hideInactive_sensor', 'false')
            context['hide_inactive'] = hide_inactive_cookie.lower() == 'true'
        
        # Add live counts to context
        context.update(get_live_counts_context(self._place))
        
        ic(context['device'].__dict__)
        ic(context['sensors'])
        ic(context['locations'])
        return context

class DeviceCreateView(LoginRequiredMixin, PlaceAnnotationMixin, CreateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'
    object: Device

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place and locations
        self._place = self.get_place()
        self._locations = get_annotated_locations(self._place)
        
        # Initialize location and inactive_help_text
        self._location = None
        self._inactive_help_text = None
        
        # Get location if specified in URL
        location_slug = self.kwargs.get('location_slug', None)
        if location_slug:
            self._location = get_object_or_404(Location, slug=location_slug, place=self._place)
            
            # If location is inactive, create help text about that
            if self._location and not self._location.is_active:
                self._inactive_help_text = mark_safe(
                    '<div class="form-text text-warning-emphasis mt-2">'
                    '<i class="bi bi-exclamation-triangle me-2"></i>This device will be inactive because Location "{self._location.name}" is inactive.'
                    '</div>'
                )

    def get_initial(self):
        initial = super().get_initial()
        duplicate_pk = self.request.GET.get('duplicate')

        if duplicate_pk:
            try:
                device_to_duplicate = get_object_or_404(Device, pk=duplicate_pk, location__place=self._place)
                
                initial['name'] = f"{device_to_duplicate.name}_Dup"
                initial['is_active'] = device_to_duplicate.is_active
                initial['is_lorawan'] = device_to_duplicate.is_lorawan
                initial['location'] = device_to_duplicate.location
                initial['device_type'] = device_to_duplicate.device_type
                initial['manufacturer'] = device_to_duplicate.manufacturer
                initial['model'] = device_to_duplicate.model
                initial['device_id'] = '' # Intentionally left blank
                
            except Device.DoesNotExist:
                pass # Or handle error appropriately
        
        return initial
        
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['place'] = self._place
        kwargs['locations'] = self._locations
        kwargs['inactive_help_text'] = self._inactive_help_text
        
        # Set initial data properly
        initial = self.get_initial()
        initial.update(kwargs.get('initial', {}))
        initial['referrer'] = self.request.GET.get('next', self.request.META.get('HTTP_REFERER', ''))
        kwargs['initial'] = initial
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['place'] = self._place
        context['locations'] = self._locations

        # Determine the location from the form's initial data if available
        location = self._location
        if not location and 'form' in context:
            location = context['form'].initial.get('location')

        if location:
            context['location'] = location

        # Set a fallback cancel URL
        # If location has a slug, go to location_detail, otherwise go to device_list
        if location and hasattr(location, 'slug') and location.slug:
            context['cancel_fallback_url'] = reverse('sensors:location_detail', kwargs={
                'place_slug': self._place.slug,
                'slug': location.slug
            })
        else:
            context['cancel_fallback_url'] = reverse('sensors:device_list', kwargs={
                'place_slug': self._place.slug
            })
        
        return context

    def get_success_url(self):
        """
        Determine the URL to redirect to on successful form submission.
        - First, try the 'referrer' from the form's POST data.
        - Fallback to the detail view of the created device.
        """
        referrer_url = self.request.POST.get('referrer')
        if referrer_url:
            return referrer_url
        
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.object.location.place.slug, 
            'pk': self.object.pk
        })

    def form_valid(self, form):
        # If no location is provided, assign the 'Unassigned' location for the place
        if not form.instance.location:
            form.instance.location = self._place.get_unassigned_location()
        
        # Save the form to get the object
        self.object = form.save()
        device = self.object
        
        # Build the message based on whether location is set
        if device.location:
            message = (
                f"Created device <strong>{device.name}</strong> in "
                f"<i class='bi bi-house-gear'></i> {device.location.place.name} > "
                f"<i class='bi bi-geo-alt'></i> {device.location.name}<br>"
            )
        else:
            message = (
                f"Created unassigned device <strong>{device.name}</strong> in "
                f"<i class='bi bi-house-gear'></i> {self._place.name}<br>"
            )

        message += (
            f"<small class='text-muted'>"
            f"Type: {device.device_type or '-'}<br>"
            f"Model: {device.model or '-'}<br>"
            f"Status: {'Active' if device.is_active else 'inactive'}"
            f"</small>"
        )
        
        # Add inactive warning to message if device is inactive
        if not device.is_active and self._inactive_help_text:
            message += f"<br><small class='text-warning'>{self._inactive_help_text}</small>"
        
        # Set toast message directly on request for middleware
        setattr(self.request, 'toast_message', {
            'message': message,
            'type': 'success' if form.cleaned_data.get('is_active', True) else 'warning'
        })
        
        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)

    def form_invalid(self, form):
        return super().form_invalid(form)


class DeviceUpdateView(LoginRequiredMixin, PlaceAnnotationMixin, UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'sensors/device_form.html'
    object: Device

    def get_queryset(self) -> QuerySet[Device]:
        if not hasattr(self, '_queryset'):
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            base_queryset = super().get_queryset()
            self._queryset = base_queryset.filter(location__place=place).prefetch_related(
                Prefetch(
                    'sensors',
                    queryset=Sensor.objects.order_by('-is_active', Lower('name')),
                    to_attr='sensors_sorted'
                )
            )
        return self._queryset

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place and locations
        self._place = self.get_place()
        self._locations = get_annotated_locations(self._place)
        
        # Default inactive_help_text to None
        self._inactive_help_text = None
        self._sensors_active = []
        
        try:
            # Try to get the device if we're updating
            device = self.get_object()
            location = device.location
            
            # Get help text based on device active state and its location
            self._inactive_help_text = self.get_device_inactive_help_text(device, location)
            
        except Exception as e:
            # If we can't get the object yet (e.g., in a GET request before the object exists)
            pass

    def get_device_inactive_help_text(self, device, location=None):
        """
        Generate help text for device inactive status.
        
        Args:
            device: The device object
            location: The device's location (optional)
            
        Returns:
            str: help_text HTML string with warning message or None
        """
        inactive_help_text = None
        sensors_active = []
        
        if not device:
            return None
            
        if not location:
            location = device.location
            
        # If location is inactive, create help text about that
        if location and not location.is_active:
            # Check if device is active when it shouldn't be
            if device and device.is_active:
                # Get the list of affected sensors before fixing
                # Convert queryset to list to ensure it's iterable
                sensors_active = list(device.sensors.filter(is_active=True).annotate(
                    reading_count=Count('readings')
                ))
                
                # Fix the inconsistency - set device to inactive
                device.is_active = False
                device.save()
            
            # Standard message for inactive location
            inactive_help_text = mark_safe(
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                f'This device will be inactive because Location "{location.name}" is inactive.'
            )
        # If device is being set to inactive or viewing an inactive device, check for active sensors
        elif device:
            # Get active sensors with reading counts - convert queryset to list
            sensors_active = list(device.sensors.filter(is_active=True).annotate(
                reading_count=Count('readings')
            ))
            
            active_sensor_count = len(sensors_active)
            
            if active_sensor_count > 0:
                # Generate the list of active sensors with their reading counts
                active_sensors_list = ''.join([
                    f'<li><i class="bi bi-thermometer text-muted me-1"></i>{sensor.name} '
                    f'<small class="text-muted">({sensor.reading_count} readings)</small></li>'
                    for sensor in sensors_active
                ])
                
                inactive_help_text = mark_safe(
                    '<i class="bi bi-exclamation-triangle me-2"></i>'
                    f'This device has {active_sensor_count} active sensor{"s" if active_sensor_count > 1 else ""}:'
                    f'<ul class="list-unstyled mb-0 mt-1 ms-4">{active_sensors_list}</ul>'
                )
        
        # Store the active sensors list for later use - make sure it's a list
        self._sensors_active = sensors_active if isinstance(sensors_active, list) else list(sensors_active)
        
        return inactive_help_text

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
        
        # Pass the referrer from initial data to the form
        kwargs['initial'] = self.get_initial()
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'device'
        context['place'] = self._place
        device = self.get_object()
        
        # Add sensors to context
        if hasattr(device, 'sensors_sorted'):
            context['sensors'] = device.sensors_sorted
            
        # Add location to context
        if device.location:
            context['location'] = get_annotated_locations(self._place).get(pk=device.location.pk)
        
        # Add a fallback cancel URL based on whether we have a location_pk
        location_slug = self.kwargs.get('location_slug', None)
        if location_slug:
            # If we have a location_pk, go to location_detail
            context['cancel_fallback_url'] = reverse('sensors:location_detail', kwargs={
                'place_slug': self._place.slug,
                'slug': self._location.slug
            })
        else:
            # If no location_pk, go to device_list
            context['cancel_fallback_url'] = reverse('sensors:device_list', kwargs={
                'place_slug': self._place.slug
            })
        
        # Add a fallback cancel URL
        context['cancel_fallback_url'] = reverse('sensors:device_detail', kwargs={
            'place_slug': self._place.slug,
            'pk': self.object.pk
            })
        
        return context

    def get_success_url(self):
        return reverse('sensors:device_detail', kwargs={
            'place_slug': self.object.location.place.slug,
            'pk': self.object.pk
        })

    def form_valid(self, form):
        # Store original values before save
        original_is_active = self.object.is_active
        original_location = self.object.location

        # Save the form but don't commit yet to check changes
        device = form.save(commit=False)

        # Retrieve the place from the setup method
        place = self._place

        # Handle the case where location is cleared (set to None)
        if 'location' in form.changed_data and form.cleaned_data['location'] is None:
            device.location = place.get_unassigned_location()
        
        # If location is not cleared, or it's a new location, set it
        elif 'location' in form.cleaned_data and form.cleaned_data['location']:
            device.location = form.cleaned_data['location']

        # Now, save the device with all changes
        device.save()
        self.object = device  # Update the view's object

        # Check if the location has changed and update toast message
        new_location = self.object.location
        location_changed = original_location != new_location
        status_changed = original_is_active != self.object.is_active

        toast_message = self.construct_toast_message(
            form, 
            status_changed, 
            location_changed, 
            original_location
        )

        setattr(self.request, 'toast_message', toast_message)
        
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        return super().form_invalid(form)

    def construct_toast_message(self, form, status_changed, location_changed, original_location):
        device = self.object
        message_parts = [f"Updated device <strong>{device.name}</strong>"]
        details = []

        if location_changed:
            if device.location and device.location.slug != 'unassigned-devices':
                details.append(f"Moved to <i class='bi bi-geo-alt'></i> {device.location.name}")
            else:
                details.append("Moved to <i class='bi bi-question-circle'></i> Unassigned")
        
        if status_changed:
            status_text = "set to <strong class='text-success'>Active</strong>" if device.is_active else "set to <strong class='text-danger'>inactive</strong>"
            details.append(f"Status {status_text}")
        
        if not details:
            details.append("No changes detected.")

        message_parts.append("<br><small class='text-muted'>" + ", ".join(details) + "</small>")
        
        return {
            'message': "".join(message_parts),
            'type': 'success'
        }

class DeviceDeleteView(LoginRequiredMixin, PlaceAnnotationMixin, DeleteView):
    model = Device
    template_name = 'sensors/device_confirm_delete.html'
    object: Device

    def get_queryset(self) -> QuerySet[Device]:
        if not hasattr(self, '_queryset'):
            place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
            base_queryset = super().get_queryset()
            self._queryset = base_queryset.filter(location__place=place)
        return self._queryset

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place
        self._place = self.get_place()
        
        # Create inactive help text to be used in form and toast messages
        try:
            device = self.get_object()
            location = device.location
            
            if location and not location.is_active:
                self._inactive_help_text = mark_safe(
                    '<i class="bi bi-exclamation-triangle me-2"></i>'
                    f'This device is inactive because Location "{location.name}" is inactive.'
                )
            else:
                self._inactive_help_text = None
        except Exception as e:
            # ic(f"Error in DeviceDeleteView.setup: {str(e)}")
            self._inactive_help_text = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add place to context for template
        context['place'] = self._place
        
        # Get the device's location
        device = self.get_object()
        if device and hasattr(device, 'location'):
            context['location'] = device.location
            
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        device = self.object
        place = self._place
        location = device.location
        
        # Before we delete the device, store its data
        device_data = {
            'name': device.name,
            'is_active': device.is_active,
            'device_type': device.device_type.name if device.device_type else '',
            'icon': device.device_type.icon if device.device_type else 'bi-hdd',
            'model': device.model or '',
            'manufacturer': device.manufacturer or '',
            'device_id': device.device_id or ''
        }
        
        # Get active sensors before deletion
        active_sensors = device.sensors.filter(is_active=True)
        sensors_info = [sensor.name for sensor in active_sensors]
        
        message = (
            f"Deleted device <strong>{device_data['name']}</strong> from "
            f"<i class='bi bi-diagram-3'></i> {location.name}<br>"
            f"<small class='text-muted'>"
            f"Type: {device_data['device_type']}<br>"
            f"Model: {device_data['model']}<br>"
            f"Manufacturer: {device_data['manufacturer']}<br>"
            f"ID: {device_data['device_id']}<br>"
            f"Active: {'Yes' if device.is_active else 'No'}"
        )
        
        if sensors_info:
            message += "<br>Affected active sensors:<ul class='mb-0'>"
            for sensor_name in sensors_info:
                message += f"<li>{sensor_name}</li>"
            message += "</ul>"
        
        message += "</small>"

        # Create toast message with device data
        request.toast_message = {
            'message': message,
            'type': 'warning'
        }
        
        # Delete the device
        device.delete()
        
        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return reverse('sensors:place_detail', 
                      kwargs={'place_slug': self._place.slug})

# class DeviceMoveLocationView(LoginRequiredMixin, View):

#     def post(self, request, pk):
#         # Get the device and validate it exists
#         # device = get_object_or_404(Device, pk=pk)
        
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