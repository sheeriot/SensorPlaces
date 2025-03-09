from influxdb_client_3 import InfluxDBClient3 as InfluxDBClient
from django.conf import settings
from datetime import datetime
from django.utils.safestring import mark_safe

def get_influxdb_client(influx_source):
    return InfluxDBClient(
        host=f"http://{influx_source.server_dns}:{influx_source.server_port}",
        token=influx_source.read_token,
        org=influx_source.org,
        database=influx_source.bucket_name
    )

def get_sensor_readings(sensor, start=None, stop=None, limit=100):
    if not sensor.influx_source or sensor.data_type != 'INFLUX':
        return []

    client = get_influxdb_client(sensor.influx_source)
    
    query = f'''
    SELECT *
    FROM "{sensor.influx_measurement}"
    WHERE sensor_id = '{sensor.id}'
    AND time >= {start if start else "NOW() - 7d"}
    AND time <= {stop if stop else "NOW()"}
    LIMIT {limit}
    '''
    
    try:
        result = client.query(query)
        readings = []
        for record in result:
            readings.append({
                'time': record['time'],
                'value': record['value'],
            })
        return readings
    except Exception as e:
        print(f"Error querying InfluxDB: {e}")
        return []
    finally:
        client.close()

def add_toast_message(request, title, message, message_type='success', duration=5000):
    """
    Add a toast message to the session.
    
    Args:
        request: The HTTP request object
        title: Title of the toast message (not used, kept for backward compatibility)
        message: Main message content (can include HTML)
        message_type: Type of message ('success', 'error', 'info', 'warning')
        duration: How long to show the toast in milliseconds (not used, kept for backward compatibility)
    """
    if 'toast_message' not in request.session:
        request.session['toast_message'] = {}
    
    request.session['toast_message'] = {
        'message': mark_safe(message),
        'type': message_type,
        'addToHistory': True
    }
    request.session.modified = True 