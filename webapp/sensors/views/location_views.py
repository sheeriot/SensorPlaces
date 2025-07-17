from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin
# from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count, Q, Sum
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.utils.safestring import mark_safe

from ..models import Place, Location, Device, Sensor
from .location_forms import LocationForm
from .mixins import PlaceAnnotationMixin, FormDataMixin
from .views_fun import get_place_counts, get_annotated_locations

from icecream import ic

# Location Views
class LocationListView(LoginRequiredMixin, PlaceAnnotationMixin, ListView):
    model = Location
    context_object_name = 'locations'
    template_name = 'sensors/location_list.html'

    def get_queryset(self) -> QuerySet[Location]:
        """Get locations with device and sensor counts."""
        place = self._place
        
        return Location.objects.filter(
            place=place
        ).annotate(
            devices_active_count=Count('devices', filter=Q(devices__is_active=True)),
            devices_inactive_count=Count('devices', filter=Q(devices__is_active=False)),
            sensors_active_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=True)),
            sensors_inactive_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=False))
        ).order_by(
            '-is_active',
            Lower('name')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        place = context['place']

        # Add hide_inactive state from cookie
        hide_inactive_cookie = self.request.COOKIES.get('hideInactive_location', 'false')
        context['hide_inactive'] = hide_inactive_cookie.lower() == 'true'

        # Add place statistics from views_fun.py
        context.update(get_place_counts(place))
        
        return context

class LocationDetailView(LoginRequiredMixin, PlaceAnnotationMixin, DetailView):
    model = Location
    context_object_name = 'location'
    template_name = 'sensors/location_detail.html'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        
        # Check for hide_inactive cookie
        hide_inactive_cookie = self.request.COOKIES.get('hideInactive_device', 'false')
        context['hide_inactive'] = hide_inactive_cookie.lower() == 'true'
        
        # Use the annotated location data from views_fun.py
        location = get_annotated_locations(self._place).get(slug=self.object.slug)
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

class LocationCreateView(LoginRequiredMixin, PlaceAnnotationMixin, FormDataMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'
    object: Location
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place 
        self._place = self.get_place()
        self._inactive_help_text = None
        
        # Generate help text if place is inactive
        if self._place and not self._place.is_active:
            self._inactive_help_text = self.get_location_inactive_help_text(None, self._place)[0]
        
        # Get the referrer URL
        self._referrer = request.META.get('HTTP_REFERER', '')

    def get_success_url(self):
        """Return the URL to redirect to after processing a valid form."""
        if self.object:
            return reverse('sensors:location_detail', kwargs={
                'place_slug': self.kwargs['place_slug'],
                'slug': self.object.slug
            })
        return reverse('sensors:location_list', kwargs={
            'place_slug': self.kwargs['place_slug']
        })

    def get_location_inactive_help_text(self, location, place=None):
        """
        Generate help text for location inactive status when creating.
        
        Args:
            location: The location object (None for create view)
            place: The location's place
            
        Returns:
            tuple: (help_text, active_devices)
                - help_text: HTML string with warning message or None
                - active_devices: empty list for create view
        """
        inactive_help_text = None
        
        # For create view, we only care about place being inactive
        if place and not place.is_active:
            inactive_help_text = mark_safe(
                '<div class="form-text text-warning-emphasis mt-2">'
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                f'This location will be inactive because Place "{place.name}" is inactive. '
                f'All devices within it will not collect data.'
                '</div>'
            )
        
        return inactive_help_text, []

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        
        # Set initial data properly - everything else comes from FormDataMixin
        kwargs['initial'] = kwargs.get('initial', {})
        kwargs['initial'].update({
            'is_active': self._place.is_active,
            'place': self._place.pk,  # Use the primary key, not the object
            'referrer': self._referrer
        })
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
        
        # Add a fallback cancel URL
        if self.object and self.object.pk:
            context['cancel_fallback_url'] = reverse('sensors:location_detail', kwargs={
                'place_slug': self._place.slug,  # Use cached place
                'slug': self.object.slug
            })
        else:
            context['cancel_fallback_url'] = reverse('sensors:place_detail', kwargs={
                'place_slug': self._place.slug  # Use cached place
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

    def add_toast_message(self, message, type='info'):
        """Add a toast message to the request."""
        # Get the place from self.get_place() (set in PlaceAnnotationMixin.setup)
        place = self.get_place()
        
        # Create toast data dict
        toast_data = {
            'message': message,
            'type': type
        }
        
        # Initialize toast_message list if it doesn't exist
        if not hasattr(self.request, 'toast_message'):
            self.request.toast_message = []
        
        # If it's a single message (not a list), convert to list
        elif not isinstance(self.request.toast_message, list):
            self.request.toast_message = [self.request.toast_message]
        
        # Add the new toast message
        self.request.toast_message.append(toast_data)
        
        return toast_data

class LocationUpdateView(LoginRequiredMixin, PlaceAnnotationMixin, FormDataMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'sensors/location_form.html'
    context_object_name = 'location'
    slug_url_kwarg = 'slug'
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place
        self._place = self.get_place()
        self._inactive_help_text = None
        self._devices_active = []
        
        # Get the referrer URL
        self._referrer = request.META.get('HTTP_REFERER', '')
        
        try:
            # Try to get the location if we're updating
            location = self.get_object()
            
            # Use the helper method to get the appropriate help text
            self._inactive_help_text, self._devices_active = self.get_location_inactive_help_text(location, self._place)
        except Exception as e:
            # If we can't get the object yet (e.g., in a GET request before the object exists)
            # Just use default help text
            self._inactive_help_text = mark_safe(
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                'This location is inactive. All devices within it will not collect data.'
            )

    def get_success_url(self):
        """Return the URL to redirect to after processing a valid form."""
        if self.object:
            return reverse('sensors:location_detail', kwargs={
                'place_slug': self.kwargs['place_slug'],
                'slug': self.object.slug
            })
        return reverse('sensors:location_list', kwargs={
            'place_slug': self.kwargs['place_slug']
        })

    def get_location_inactive_help_text(self, location, place=None):
        """
        Generate help text for location inactive status.
        
        Args:
            location: The location object
            place: The location's place (optional)
            
        Returns:
            tuple: (help_text, active_devices)
                - help_text: HTML string with warning message or None
                - active_devices: list of active devices for this location or []
        """
        inactive_help_text = None
        devices_active = []
        
        if not location:
            return None, []
            
        if not place:
            place = location.place
            
        # If place is inactive, create help text about that
        if place and not place.is_active:
            # Check if location is active when it shouldn't be
            if location and location.is_active:
                # Get the list of affected devices before fixing
                devices_active = list(location.devices.filter(is_active=True).annotate(
                    sensor_count=Count('sensors', filter=Q(sensors__is_active=True))
                ).prefetch_related('sensors'))
                
                # Fix the inconsistency - set location to inactive
                location.is_active = False
                location.save()
                
                # Just log the inconsistency with ic
                # ic(f"Fixed inconsistency: Location {location.id} ({location.name}) was active "
                #    f"but its Place {place.id} ({place.name}) is inactive.")
                # ic(f"Affected devices: {len(devices_active)}")
            
            # Standard message for inactive place
            inactive_help_text = mark_safe(
                '<div class="form-text text-warning-emphasis mt-2">'
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                f'This location will be inactive because Place "{place.name}" is inactive. '
                f'All devices within it will not collect data.'
                '</div>'
            )
        # If location is active, check for active devices
        elif location and location.is_active:
            # Get active devices with sensor counts
            devices_active = list(location.devices.filter(is_active=True).annotate(
                sensor_count=Count('sensors', filter=Q(sensors__is_active=True))
            ).prefetch_related('sensors'))
            
            active_device_count = len(devices_active)
            
            if active_device_count > 0:
                # Generate the list of active devices with their sensor counts
                active_devices_list = ''.join([
                    f'<li><i class="bi bi-hdd-rack text-muted me-1"></i>{device.name} '
                    f'<small class="text-muted">({device.sensor_count} active sensors)</small></li>'
                    for device in devices_active
                ])
                
                inactive_help_text = mark_safe(
                    '<div class="form-text text-warning-emphasis mt-2">'
                    f'<i class="bi bi-exclamation-triangle me-2"></i>'
                    f'This location has {active_device_count} active device{"s" if active_device_count > 1 else ""}:'
                    f'<ul class="list-unstyled mb-0 mt-1 ms-4">{active_devices_list}</ul>'
                    '</div>'
                )
        
        return inactive_help_text, devices_active

    def get_initial(self):
        initial = super().get_initial()
        # Set the referrer in initial data
        initial['referrer'] = self.request.META.get('HTTP_REFERER', '')
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        
        # Set initial data properly - everything else comes from FormDataMixin
        kwargs['initial'] = kwargs.get('initial', {})
        kwargs['initial'].update({
            'referrer': self._referrer
        })
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'location'
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
        
        # Add a fallback cancel URL
        if self.object and self.object.pk:
            context['cancel_fallback_url'] = reverse('sensors:location_detail', kwargs={
                'place_slug': self._place.slug,  # Use cached place
                'slug': self.object.slug
            })
        else:
            context['cancel_fallback_url'] = reverse('sensors:place_detail', kwargs={
                'place_slug': self._place.slug  # Use cached place
            })
        
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
        if original_values['slug'] != form.cleaned_data['slug']:
            changes.append(f"Slug: {original_values['slug']} → {form.cleaned_data['slug']}")
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
        toast_message = {
            'message': message,
            'type': 'success' if form.cleaned_data['is_active'] else 'warning'
        }
        
        # Debug statements
        # ic("⚠️ Setting toast_message on request:", toast_message)
        
        # Set on request
        setattr(self.request, 'toast_message', toast_message)
        
        # ALSO set directly in session for reliability
        if hasattr(self.request, 'session'):
            self.request.session['pending_toast'] = toast_message
            self.request.session.modified = True
            # ic("⚠️ Also set pending_toast in session")
        
        # Get the success URL and return HttpResponseRedirect
        success_url = self.get_success_url()
        # ic("⚠️ Redirecting to:", success_url)
        
        return HttpResponseRedirect(success_url)

class LocationDeleteView(LoginRequiredMixin, PlaceAnnotationMixin, DeleteView):
    model = Location
    template_name = 'sensors/location_confirm_delete.html'
    slug_url_kwarg = 'slug'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # Get and cache place
        self._place = self.get_place()
        
        # Create inactive help text to be used in form and toast messages
        if self._place and not self._place.is_active:
            self._inactive_help_text = mark_safe(
                '<i class="bi bi-exclamation-triangle me-2"></i>'
                f'This location is inactive because Place "{self._place.name}" is inactive.'
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
