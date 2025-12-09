from django import template
from sensors.models import Sensor

register = template.Library()

@register.filter(name='format_boolean')
def format_boolean(value, sensor_type_name):
    """
    Formats a boolean value based on the sensor type.
    - 'Switch' -> 'On'/'Off'
    - Other booleans -> 'True'/'False'
    """
    is_true = value not in [0, 0.0, '0', '0.0', False, 'false', 'False', None]

    if sensor_type_name == 'Switch':
        return 'On' if is_true else 'Off'

    return 'True' if is_true else 'False'
