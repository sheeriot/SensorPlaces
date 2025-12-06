from django.db.models import Count, Q, F, Prefetch
from django.db.models.functions import Lower
from decimal import Decimal
from typing import Dict, Any
from django.urls import reverse
import json

from ..models import Place, Location, Device, Sensor, SensorType, Unit, DeviceType

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
    """
    Returns a queryset of locations for a given place, annotated with device and sensor counts.
    """
    return Location.objects.filter(place=place).annotate(
        devices_active_count=Count('devices', filter=Q(devices__is_active=True), distinct=True),
        devices_inactive_count=Count('devices', filter=Q(devices__is_active=False), distinct=True),
        sensors_active_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=True), distinct=True),
        sensors_inactive_count=Count('devices__sensors', filter=Q(devices__sensors__is_active=False), distinct=True)
    ).order_by('-is_active', Lower('name'))

def get_location_data(location) -> Dict[str, Any]:
    """Convert a Location instance to a JSON-serializable dictionary."""
    return {
        'id': str(location.pk),
        'slug': str(location.slug),
        'name': str(location.name),
        'x_pos': float(location.x_pos) if isinstance(location.x_pos, Decimal) else location.x_pos,
        'y_pos': float(location.y_pos) if isinstance(location.y_pos, Decimal) else location.y_pos,
        'is_active': bool(location.is_active),
        'devices_active_count': getattr(location, 'devices_active_count', 0)
    }

def get_place_counts(place):
    """Get device and sensor counts for a place.

    Returns a tuple of six values:
    - locations_active_count
    - locations_inactive_count
    - devices_active_count
    - devices_inactive_count
    - sensors_active_count
    - sensors_inactive_count
    """
    locations_active_count = Location.objects.filter(place=place, is_active=True).exclude(name="Unassigned Devices").count()
    locations_inactive_count = Location.objects.filter(place=place, is_active=False).exclude(name="Unassigned Devices").count()

    # Correctly count active devices by checking the entire hierarchy.
    # An active device requires its location and place to also be active.
    devices_active_count = Device.objects.filter(
        location__place=place,
        is_active=True,
        location__is_active=True,
        location__place__is_active=True
    ).count()

    # Inactive devices are any devices that do not meet the "active" criteria.
    total_devices = Device.objects.filter(location__place=place).count()
    devices_inactive_count = total_devices - devices_active_count

    # Correctly count active sensors, also checking the full hierarchy.
    sensors_active_count = Sensor.objects.filter(
        device__location__place=place,
        is_active=True,
        device__is_active=True,
        device__location__is_active=True,
        device__location__place__is_active=True
    ).count()

    # Inactive sensors are any sensors that do not meet the "active" criteria.
    total_sensors = Sensor.objects.filter(device__location__place=place).count()
    sensors_inactive_count = total_sensors - sensors_active_count

    return locations_active_count, locations_inactive_count, devices_active_count, devices_inactive_count, sensors_active_count, sensors_inactive_count

def get_place_data(place, request=None, include_json=True):
    """Get complete place data including locations and statistics.

    Returns a dictionary with all place-related data.
    """
    import json

    # Get annotated locations
    result = {}

    # Prefetch devices and their sensors to avoid N+1 queries in the template.
    # This is the key to making the device list card work correctly.
    devices_prefetch = Prefetch(
        'devices',
        queryset=Device.objects.select_related('device_type').annotate(
            sensors_active_count=Count('sensors', filter=Q(sensors__is_active=True), distinct=True),
            sensors_inactive_count=Count('sensors', filter=Q(sensors__is_active=False), distinct=True)
        ).prefetch_related(
            Prefetch('sensors', queryset=Sensor.objects.order_by('-is_active', Lower('name')), to_attr='sensors_sorted')
        ).order_by('-is_active', Lower('name')),
        to_attr='devices_sorted'
    )

    locations = get_annotated_locations(place).prefetch_related(devices_prefetch).order_by('-is_active', Lower('name'))

    result['locations'] = locations

    # Add hide_inactive state from request if available
    if request:
        hide_inactive_cookie = request.COOKIES.get('hideInactive_location', 'false')
        result['hide_inactive'] = hide_inactive_cookie.lower() == 'true'
    else:
        result['hide_inactive'] = False # Default if no request

    # Add JSON data if requested
    if include_json:
        locations_data = [get_location_data(loc) for loc in locations]
        result['locations_json'] = locations_data

    # Add statistics
    locations_active, locations_inactive, devices_active, devices_inactive, sensors_active, sensors_inactive = get_place_counts(place)
    result.update({
        'locations_active_count': locations_active,
        'locations_inactive_count': locations_inactive,
        'devices_active_count': devices_active,
        'devices_inactive_count': devices_inactive,
        'sensors_active_count': sensors_active,
        'sensors_inactive_count': sensors_inactive
    })

    return result

def get_live_counts_context(place):
    locations_active, locations_inactive, devices_active, devices_inactive, sensors_active, sensors_inactive = get_place_counts(place)
    return {
        'locations_active': locations_active,
        'locations_inactive': locations_inactive,
        'devices_active': devices_active,
        'devices_inactive': devices_inactive,
        'sensors_active': sensors_active,
        'sensors_inactive': sensors_inactive
    }


def create_switchbot_device(device_item, location, sensor_types, stdout, style):
    """Helper function to create a single device, returns 1 if created, 0 otherwise."""
    device_id = device_item['deviceId']

    device, created = Device.objects.get_or_create(
        device_id=device_id,
        defaults={
            'name': device_item['deviceName'],
            'model': device_item.get('deviceType', 'Unknown'),
            'manufacturer': 'SwitchBot',
            'is_switchbot': True,
            'switchbot_hub_device_id': device_item.get('hubDeviceId'),
            'location': location,
            'is_active': not location.slug == 'unassigned-devices'
        }
    )

    if created:
        api_device_type_str = device.model

        if 'Hub' in api_device_type_str:
            device_type_name = "SwitchBot Hub"
        else:
            device_type_name = api_device_type_str

        device_type, _ = DeviceType.objects.get_or_create(
            name=device_type_name,
            defaults={'description': f'A {device_type_name} from SwitchBot.'}
        )
        device.device_type = device_type
        device.save()
        stdout.write(style.SUCCESS(f"Imported new device: {device.name} ({device_id})"))

    # Auto-create sensors for meter devices
    api_device_type_str = device.model
    meter_types = ["Meter", "Meter Plus", "Outdoor Meter", "Meter Pro", "WoSensorTH", "WoIOSensor"]
    if any(meter_type in api_device_type_str for meter_type in meter_types):

        s1, s1_created = Sensor.objects.get_or_create(
            device=device,
            sensor_type=sensor_types['temperature'],
            defaults={'name': f'{device.name} Temperature', 'is_active': device.is_active}
        )
        s2, s2_created = Sensor.objects.get_or_create(
            device=device,
            sensor_type=sensor_types['humidity'],
            defaults={'name': f'{device.name} Humidity', 'is_active': device.is_active}
        )
        s3, s3_created = Sensor.objects.get_or_create(
            device=device,
            sensor_type=sensor_types['battery'],
            defaults={'name': f'{device.name} Battery', 'is_active': device.is_active}
        )

        if created or any([s1_created, s2_created, s3_created]):
                stdout.write(style.SUCCESS(f"    - Ensured Temperature, Humidity, and Battery sensors for {device.name}."))

    return 1 if created else 0
