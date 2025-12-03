# webapp/sensors/services/measurement_utils.py

# A map to group sensor types into a single InfluxDB measurement.
# This helps organize related data, e.g., temperature and humidity under "climate".
# Format: 'Sensor Type Name': ('influx_measurement_name', 'influx_field_name')
INFLUX_GROUP_MAP = {
    # Climate
    'Temperature': ('climate', 'temperature'),
    'Humidity': ('climate', 'humidity'),
    'Light Level': ('climate', 'light_level'),

    # Power
    'Power': ('powermon', 'power'),
    'Current': ('powermon', 'current'),
    'Voltage': ('voltage', 'voltage'), # Often reported separately

    # Battery
    'Battery Level': ('battery', 'percent'),
    'Battery Voltage': ('battery', 'voltage'),

    # Environmental
    'Water Detector': ('flood', 'flood'),
    'PM2.5': ('air_quality', 'pm25'),
}

def get_influx_details(sensor_type_name: str) -> tuple | None:
    """
    Returns the InfluxDB measurement and field name for a given sensor type name.

    Args:
        sensor_type_name: The friendly name of the sensor type (e.g., "Temperature").

    Returns:
        A tuple of (measurement_name, field_name) or None if not found.
    """
    return INFLUX_GROUP_MAP.get(sensor_type_name)
