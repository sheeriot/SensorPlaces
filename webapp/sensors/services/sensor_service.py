import logging
from icecream import ic
from django.utils import timezone
from sensors.models import Sensor, SensorReading, SensorType, Device

logger = logging.getLogger(__name__)

def process_sensor_reading(device: Device, measurement_type: str, value: float, skip_local_storage: bool = False):
    """
    Helper to store sensor reading in local DB. Finds or creates a sensor.
    Returns the sensor object on success, None otherwise.
    """
    try:
        # Try to find a sensor with a type matching the measurement name
        sensor = Sensor.objects.filter(
            device=device,
            sensor_type__name__iexact=measurement_type
        ).first()

        # If not found, try matching by sensor name directly
        if not sensor:
            sensor = Sensor.objects.filter(
                device=device,
                name__iexact=measurement_type
            ).first()

        created = False
        if not sensor:
            sensor_type = SensorType.objects.filter(name__iexact=measurement_type).first()
            # Ensure name is human-readable (replace underscores with spaces)
            sensor_name = measurement_type.replace('_', ' ').title()

            # Initial default data_type is DIRECT (from model default)
            sensor = Sensor.objects.create(
                device=device,
                name=sensor_name,
                sensor_type=sensor_type,
                is_active=device.is_active,
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

            ic(f"Updating Sensor Reading for {sensor.name}: Value={value}")

            if not skip_local_storage:
                SensorReading.objects.create(
                    sensor=sensor,
                    value=value,
                    value_boolean=val_bool
                )

            sensor.cached_reading_value = value
            sensor.cached_reading_timestamp = timezone.now()
            sensor.last_checked_timestamp = timezone.now()
            sensor.save(update_fields=['cached_reading_value', 'cached_reading_timestamp', 'last_checked_timestamp'])

            return sensor

        return None

    except Exception as e:
        logger.error(f"Error saving local sensor reading for {device.name}: {e}")
        return None
