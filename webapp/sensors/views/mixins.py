# from django.db.models import Count, Q

from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from django.core.exceptions import ImproperlyConfigured

from django.http import HttpRequest
from decimal import Decimal

from ..models import Place, Location
from .views_fun import get_annotated_locations

from typing import Any, Dict, Optional

from icecream import ic


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
        """Get annotated locations for a place."""
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
        if 'place' not in context:
            context['place'] = place
        
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
                kwargs['locations'] = self.get_annotated_locations(place)
        
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
