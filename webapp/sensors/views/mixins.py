from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from django.core.exceptions import ImproperlyConfigured

from ..models import Place, Location, Device, Sensor

import json
from decimal import Decimal

from icecream import ic


# First the Mixin that makes summarizes Locations data for all Place views.
class PlaceAnnotationMixin:
    """Mixin to add annotated locations to context data."""
    
    kwargs: dict

    def get_place(self) -> Place:
        """Get the place object from the URL kwargs.
        
        Returns:
            Place: The place object for this view
            
        Raises:
            Http404: If place_slug is not in kwargs or Place does not exist
        """
        place_slug = self.kwargs.get('place_slug', None)
        if not place_slug:
            raise ImproperlyConfigured(
                f"View {self.__class__.__name__} must be called with place_slug in URL kwargs"
            )

        try:
            self.place = get_object_or_404(Place, slug=place_slug)
        except Exception as e:
            # ic('-get place error:', e)
            raise ValueError(f"Place with slug {place_slug} not found")
        return self.place
    
    def get_location_data(self, location: Location) -> dict:
        """Convert a Location instance to a JSON-serializable dictionary.
        
        Args:
            location: The Location model instance
            
        Returns:
            Dict containing the location data for JavaScript
        """
        return {
            'id': str(location.pk),
            'name': str(location.name),
            'x_pos': float(location.x_pos) if isinstance(location.x_pos, Decimal) else location.x_pos,
            'y_pos': float(location.y_pos) if isinstance(location.y_pos, Decimal) else location.y_pos,
            'is_active': bool(location.is_active),
            'devices_active_count': getattr(location, 'devices_active_count', 0)
        }

    def get_annotated_locations(self, place: Place) -> QuerySet[Location]:
        """Get annotated locations for a place.
        
        Args:
            place: The Place model instance
            
        Returns:
            QuerySet of Location instances with annotations
        """
        return Location.objects.filter(place=place).annotate(
            devices_active_count=Count(
                'devices',
                filter=Q(devices__is_active=True),
                distinct=True
            ),
            devices_inactive_count=Count(
                'devices',
                filter=Q(devices__is_active=False),
                distinct=True
            ),
            sensors_active_count=Count(
                'devices__sensors',
                filter=Q(devices__sensors__is_active=True),
                distinct=True
            ),
            sensors_inactive_count=Count(
                'devices__sensors',
                filter=Q(devices__sensors__is_active=False),
                distinct=True
            )
        ).order_by('-is_active', Lower('name'))

    def get_context_data(self, **kwargs) -> dict:
        """Add place and location_annotatoins and count data to the template context."""
        context = super().get_context_data(**kwargs)
        
        # Get place - this will always exist or raise an error
        place = self.get_place()
        context['place'] = place
        
        # Get annotated locations for this place
        locations = self.get_annotated_locations(place)
        
        # Convert locations to JSON-serializable format for JavaScript
        locations_data = [self.get_location_data(loc) for loc in locations]
        
        # Add place statistics using distinct counts
        context.update({
            'locations': locations,  # Full queryset for template
            'locations_json': json.dumps(locations_data),  # JSON for JavaScript
            'devices_active_count': Device.objects.filter(
                location__place=place, 
                is_active=True
            ).distinct().count(),
            'devices_inactive_count': Device.objects.filter(
                location__place=place, 
                is_active=False
            ).distinct().count(),
            'sensors_active_count': Sensor.objects.filter(
                device__location__place=place, 
                is_active=True
            ).distinct().count(),
            'sensors_inactive_count': Sensor.objects.filter(
                device__location__place=place, 
                is_active=False
            ).distinct().count(),
        })
        
        return context
