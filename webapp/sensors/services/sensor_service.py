import logging
from icecream import ic
from django.db import connection
from django.utils import timezone
from sensors.models import Sensor, SensorReading, SensorType, Device
from sensors.models import Unit

logger = logging.getLogger(__name__)

# Primary key ranges for data classification:
# - System seed data: pk < 100
# - User-created data: pk >= 100 and < 1000
# - Auto-created data (by webhooks/APIs): pk >= 1000
AUTO_CREATED_PK_START = 1000


def _get_next_auto_pk(model_class):
    """
    Get the next available primary key >= AUTO_CREATED_PK_START for auto-created records.
    """
    max_pk = model_class.objects.filter(pk__gte=AUTO_CREATED_PK_START).order_by('-pk').values_list('pk', flat=True).first()
    if max_pk is None:
        return AUTO_CREATED_PK_START
    return max_pk + 1


def get_or_create_auto_sensor_type(name: str) -> SensorType:
    """
    Get an existing SensorType by name or alias (case-insensitive) or create a new one
    with pk >= 1000 for auto-created types.

    Uses the database aliases field for matching, making type resolution configurable
    by administrators without code changes.
    """
    # First try to find an existing one by name or alias
    sensor_type = SensorType.find_by_alias(name)
    if sensor_type:
        return sensor_type

    # Create a new one with pk >= 1000
    next_pk = _get_next_auto_pk(SensorType)
    sensor_type = SensorType.objects.create(
        id=next_pk,
        name=name,
        description=f'Auto-created sensor type for {name}',
        is_system=False,  # User/auto-created, not system
    )
    ic(f"Auto-created SensorType '{name}' with pk={next_pk}")
    return sensor_type

def process_sensor_reading(
    device: Device,
    measurement_type: str,
    value: float,
    source: str = None,
    skip_local_storage: bool = False,
    activate_sensor: bool = False,
    switchbot_sensor_name: str = None
):
    """
    Finds or creates a sensor for a given measurement and updates its cached value.
    Optionally stores a historical reading in the local DB.

    Args:
        device (Device): The device the reading belongs to.
        measurement_type (str): The name/type of the measurement (e.g., "Temperature").
        value (float): The value of the reading.
        source (str, optional): The origin of the reading (e.g., 'shelly-webhook', 'switchbot-api').
        skip_local_storage (bool): If True, a historical `SensorReading` object will NOT be created.
                                   The sensor's cache fields will still be updated.
        activate_sensor (bool): If a new sensor is created, this flag determines if it's active.
        switchbot_sensor_name (str, optional): The original sensor name from the SwitchBot API.

    Returns:
        The updated Sensor object, or None on failure.
    """
    try:
        sensor = None
        # If a switchbot_sensor_name is provided, use it for lookup first
        if switchbot_sensor_name:
            sensor = Sensor.objects.filter(
                device=device,
                switchbot_sensor_name=switchbot_sensor_name
            ).first()

        # If not found, try to find a sensor with a type matching the measurement name
        if not sensor:
            sensor = Sensor.objects.filter(
                device=device,
                sensor_type__name__iexact=measurement_type
            ).first()

        # If not found, try matching by sensor name directly (legacy)
        if not sensor:
            sensor = Sensor.objects.filter(
                device=device,
                name__iexact=measurement_type
            ).first()

        created = False
        if not sensor:
            # Use find_by_alias to match by name or alias (configurable in admin)
            sensor_type = SensorType.find_by_alias(measurement_type)
            if not sensor_type:
                # Auto-create with pk >= 1000 for webhook/API-created types
                sensor_type = get_or_create_auto_sensor_type(measurement_type)

            # Ensure that boolean-type sensors have their unit set on the SensorType.
            if sensor_type and sensor_type.name in ('Switch', 'Water Detector') and not sensor_type.unit:
                bool_unit, _ = Unit.objects.get_or_create(name='Boolean')
                sensor_type.unit = bool_unit
                sensor_type.save(update_fields=['unit'])
                ic(f"Associated 'Boolean' unit with '{sensor_type.name}' SensorType.")

            # Special case for SwitchBot battery readings
            if measurement_type == 'battery':
                sensor_type = SensorType.objects.filter(name__iexact='Battery Level').first()

            # Ensure name is human-readable (replace underscores with spaces)
            sensor_name = measurement_type.replace('_', ' ').title()

            # Initial default data_store is DIRECT (from model default)
            sensor = Sensor.objects.create(
                device=device,
                name=sensor_name,
                sensor_type=sensor_type,
                is_active=activate_sensor,
                switchbot_sensor_name=switchbot_sensor_name,
            )
            created = True

            ic(sensor)
            if sensor.sensor_type:
                 ic(sensor.sensor_type)

            # Log creation
            from sensors.utils import record_webhook_activity
            place = device.location.place
            sensor_type_name = sensor.sensor_type.name if sensor.sensor_type else "None"
            message = f"WEBHOOK: New Sensor | Place: {place.name} | Device: {device.name} | Sensor: {sensor.name} | Type: {sensor_type_name}"
            record_webhook_activity(message)

        if sensor:
            # Determine value_boolean if reading is 0.0 or 1.0
            val_bool = None
            if value == 1.0:
                val_bool = True
            elif value == 0.0:
                val_bool = False

            # ic(f"Updating Sensor Reading for {sensor.name}: Value={value}")

            # Always update the cache fields on the Sensor model
            sensor.cached_reading_value = value
            sensor.cached_reading_timestamp = timezone.now()
            sensor.last_cached_timestamp = timezone.now()
            update_fields = ['cached_reading_value', 'cached_reading_timestamp', 'last_cached_timestamp']

            if source:
                sensor.cached_reading_source = source
                update_fields.append('cached_reading_source')

            # Only create a historical reading if not skipping local storage
            if not skip_local_storage:
                SensorReading.objects.create(
                    sensor=sensor,
                    value=value,
                    value_boolean=val_bool
                )
                ic(f"Created new historical reading for {sensor.name}.")

            sensor.save(update_fields=update_fields)
            # ic(f"Updated sensor cache for {sensor.name} with fields: {update_fields}")

            return sensor

        return None

    except Exception as e:
        logger.error(f"Error saving local sensor reading for {device.name}: {e}")
        return None
