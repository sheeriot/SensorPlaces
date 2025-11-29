# from django.db.models import Count, Q

from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from django.core.exceptions import ImproperlyConfigured

from django.http import HttpRequest
from decimal import Decimal

from django.urls import reverse
from django.views.generic.edit import CreateView
from .views_fun import get_annotated_locations, get_place_data

from ..models import Place, Location

from typing import Any, Dict, Optional

from icecream import ic
from django.urls import NoReverseMatch


class ReferrerMixin:
    """
    A mixin to handle the 'next' URL for successful form submissions and 'Cancel' button links.
    - It provides a standardized get_success_url that redirects to the object's detail view.
    - It provides a get_cancel_url that can be defined on the view.
    """
    request: HttpRequest

    def get_form_kwargs(self) -> Dict[str, Any]:
        """
        Pass the correct cancel_url to the form.
        Also populate the referrer field if available.
        """
        kwargs = super().get_form_kwargs()
        kwargs['cancel_url'] = self.get_cancel_url()

        # Add initial referrer if not present, to populate the hidden field
        if 'initial' not in kwargs:
            kwargs['initial'] = {}
        if 'referrer' not in kwargs['initial']:
            # Use current request's referrer
            kwargs['initial']['referrer'] = self.request.META.get('HTTP_REFERER', '')

        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Ensure the cancel_url is in the context for the template.
        """
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.get_cancel_url()
        return context

    def get_success_url(self) -> str:
        """
        Return the object's detail view URL, or the referrer if available.
        This provides a consistent redirect after a successful form submission.
        """
        # First check if there is a referrer in the POST data
        if self.request.method == 'POST':
            referrer = self.request.POST.get('referrer')
            if referrer:
                 from django.utils.http import url_has_allowed_host_and_scheme
                 if url_has_allowed_host_and_scheme(
                     url=referrer,
                     allowed_hosts={self.request.get_host()},
                     require_https=self.request.is_secure()
                 ):
                     return referrer

        if not hasattr(self.object, 'get_absolute_url'):
            raise ImproperlyConfigured(
                f"Object {self.object.__class__.__name__} does not have a get_absolute_url method."
            )
        return self.object.get_absolute_url()

    def get_cancel_url(self) -> str:
        """
        Provide a cancel URL. For create views, it's the list view.
        For update views, it's the object's detail view.
        """
        # ic("ReferrerMixin.get_cancel_url called")

        # For create views, return the list view
        if isinstance(self, CreateView):
            # Assumes the list view is named '<model_name>-list'
            # E.g., for a 'Place' model, it would be 'place-list'
            # But we can do better by looking at the model
            if hasattr(self, 'model') and self.model:
                app_label = self.model._meta.app_label
                model_name = self.model._meta.model_name

                url_name = f'{app_label}:{model_name}_list'
                url_kwargs = {}

                # If 'place_slug' is in the view's kwargs, add it to the reverse call
                if 'place_slug' in self.kwargs:
                    url_kwargs['place_slug'] = self.kwargs['place_slug']

                try:
                    return reverse(url_name, kwargs=url_kwargs)
                except NoReverseMatch:
                    # Fallback for cases where the URL structure is unexpected
                    pass

            ic("CreateView without a model, falling back.")

        # For update views, try to get the object and return its detail page URL.
        # ic(f"hasattr(self, 'get_object'): {hasattr(self, 'get_object')}")
        if hasattr(self, 'get_object'):
            try:
                # ic("Attempting to call self.get_object()")
                obj = self.get_object()
                # ic(f"self.get_object() returned: {obj}")
                if obj and hasattr(obj, 'get_absolute_url'):
                    # ic("Object has get_absolute_url, returning it.")
                    return obj.get_absolute_url()
                # ic("Object is None or does not have get_absolute_url")
            except Exception as e:
                # This will fail on a CreateView, which is expected.
                # ic(f"Exception in get_cancel_url's try block: {e}")
                pass

        # ic("No cancel URL found, returning to root.")
        return reverse('sensors:place_list')


class PlaceAnnotationMixin:
    """Mixin to retrieve and cache the place object from URL kwargs."""

    kwargs: dict
    _place: Optional[Place] = None

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        """Setup method to ensure place is set up early."""
        # Call parent setup method if it exists
        if hasattr(super(), 'setup'):
            super().setup(request, *args, **kwargs)
        self.kwargs = kwargs
        # Get place from kwargs, will raise 404 if not found
        self._place = self.get_place()

    def get_place(self) -> Place:
        """Get the place object from the URL kwargs."""
        place_slug = self.kwargs.get('place_slug', None)
        if not place_slug:
            raise ImproperlyConfigured(
                f"View {self.__class__.__name__} must be called with place_slug in URL kwargs"
            )

        return get_object_or_404(Place, slug=place_slug)

    def get_annotated_locations(self, place: Place) -> QuerySet[Location]:
        """Get annotated locations for a place using the function from views_fun.py."""
        return get_annotated_locations(place)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add place to template context."""
        # Try to get parent context, fallback to empty dict
        try:
            context = super().get_context_data(**kwargs)
        except AttributeError:
            context = {}

        # Get place - should have been set in setup
        place = getattr(self, '_place', self.get_place())

        # Always ensure place is in context
        context['place'] = place

        # If we have a place, add place data to context
        if place:
            # Add annotated locations if needed
            if 'locations' not in context:
                context['locations'] = self.get_annotated_locations(place)

        return context


class FormDataMixin:
    """Mixin that injects place and location data into form kwargs."""

    def get_form_kwargs(self) -> Dict[str, Any]:
        """Add place and locations data to form kwargs."""
        kwargs = super().get_form_kwargs()

        # Add place data if available (from PlaceAnnotationMixin)
        place = getattr(self, '_place', None)
        if place:
            kwargs['place'] = place

            # Add annotated locations if they're needed by the form
            if hasattr(self, 'get_annotated_locations'):
                kwargs['locations'] = get_annotated_locations(place)

        # Pass inactive_help_text if available
        if hasattr(self, '_inactive_help_text'):
            kwargs['inactive_help_text'] = self._inactive_help_text

        # Pass active devices if available
        if hasattr(self, '_devices_active'):
            kwargs['devices_active'] = self._devices_active

        return kwargs


class ToastMixin:
    """Mixin to add toast message helpers to views."""

    request: HttpRequest

    def add_toast(self, message: str, type: str = 'info') -> Dict[str, str]:
        """Add a single toast message."""
        toast_data = {
            'message': message,
            'type': type
        }

        # Initialize toast_message as list if doesn't exist
        if not hasattr(self.request, 'toast_message'):
            setattr(self.request, 'toast_message', [])
        # If it's a single message, convert to list
        elif not isinstance(self.request.toast_message, list):
            setattr(self.request, 'toast_message', [self.request.toast_message])

        # Add the new toast
        self.request.toast_message.append(toast_data)
        return toast_data

    def add_success_toast(self, message: str) -> Dict[str, str]:
        """Add a success toast message."""
        return self.add_toast(message, 'success')

    def add_info_toast(self, message: str) -> Dict[str, str]:
        """Add an info toast message."""
        return self.add_toast(message, 'info')

    def add_warning_toast(self, message: str) -> Dict[str, str]:
        """Add a warning toast message."""
        return self.add_toast(message, 'warning')

    def add_danger_toast(self, message: str) -> Dict[str, str]:
        """Add a danger toast message."""
        return self.add_toast(message, 'danger')
