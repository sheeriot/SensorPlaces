from django.db.models import Count, Q
from django.db.models.functions import Lower
from decimal import Decimal
from typing import Dict, Any

from ..models import Place, Location, Device, Sensor

from icecream import ic

def get_annotated_places():
    """Get annotated places with minimal counts for the landing page/index view.
    
    Optimized for performance with only essential annotations:
    - active_locations_count: Count of active locations
    - devices_active_count: Count of active devices
    
    Returns:
        QuerySet: Places with minimal annotations, ordered by active status and name.
    """
    return Place.objects.annotate(
        active_locations_count=Count('locations', filter=Q(locations__is_active=True)),
        devices_active_count=Count('locations__devices', filter=Q(locations__devices__is_active=True))
        # Removed active_sensors_count to optimize query performance
    ).order_by('-is_active', Lower('name'))

def get_annotated_locations(place):
    """Get annotated locations for a place."""
    locations = Location.objects.filter(place=place).annotate(
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

    return locations

def get_location_data(location) -> Dict[str, Any]:
    """Convert a Location instance to a JSON-serializable dictionary."""
    return {
        'id': str(location.pk),
        'name': str(location.name),
        'x_pos': float(location.x_pos) if isinstance(location.x_pos, Decimal) else location.x_pos,
        'y_pos': float(location.y_pos) if isinstance(location.y_pos, Decimal) else location.y_pos,
        'is_active': bool(location.is_active),
        'devices_active_count': getattr(location, 'devices_active_count', 0)
    }

def get_place_counts(place):
    """Get device and sensor counts for a place.
    
    Returns a dictionary with:
    - devices_active_count
    - devices_inactive_count
    - sensors_active_count
    - sensors_inactive_count
    """
    return {
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
    }

def get_place_data(place, include_json=True):
    """Get complete place data including locations and statistics.
    
    Returns a dictionary with all place-related data.
    """
    import json
    
    # Get annotated locations
    locations = get_annotated_locations(place)
    
    # Build result dictionary with proper type annotations
    result = {}
    result['locations'] = locations
    
    # Add JSON data if requested
    if include_json:
        locations_data = [get_location_data(loc) for loc in locations]
        result['locations_json'] = json.dumps(locations_data)
    
    # Add statistics
    counts = get_place_counts(place)
    result.update(counts)
    
    return result
