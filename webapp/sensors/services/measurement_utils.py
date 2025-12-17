# webapp/sensors/services/measurement_utils.py

# Legacy map for fallback during transition period.
# New sensor types should have influx_measurement and influx_field_name set in the database.
INFLUX_GROUP_MAP = {
    # Climate
    'Temperature': ('climate', 'temperature'),
    'Humidity': ('climate', 'humidity'),
    'Light Level': ('climate', 'light_level'),
    'Ambient Light': ('climate', 'light_level'),

    # Power
    'Power': ('powermon', 'power'),
    'Current': ('powermon', 'current'),
    'Voltage': ('voltage', 'voltage'),

    # Battery
    'Battery Level': ('battery', 'percent'),
    'Battery Voltage': ('battery', 'voltage'),

    # Environmental
    'Water Detector': ('flood', 'flood'),
    'Leak Detected': ('flood', 'flood'),
    'PM2.5': ('air_quality', 'pm25'),

    # Motion
    'Motion': ('motion', 'detected'),

    # Switch
    'Switch': ('switch', 'state'),
}


def get_influx_details(sensor_type) -> tuple | None:
    """
    Returns the InfluxDB measurement and field name for a given sensor type.

    Args:
        sensor_type: Either a SensorType instance or a string name.

    Returns:
        A tuple of (measurement_name, field_name) or None if not found.
    """
    # Handle string input (legacy compatibility)
    if isinstance(sensor_type, str):
        return INFLUX_GROUP_MAP.get(sensor_type)

    # Handle SensorType model instance
    if sensor_type is None:
        return None

    # Prefer database configuration
    if sensor_type.influx_measurement:
        return (sensor_type.influx_measurement, sensor_type.influx_field_name or 'value')

    # Fallback to legacy map
    return INFLUX_GROUP_MAP.get(sensor_type.name)
