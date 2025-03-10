from influxdb_client_3 import InfluxDBClient3 as InfluxDBClient
# from django.conf import settings
# from datetime import datetime
# from django.utils.safestring import mark_safe
from icecream import ic

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

def add_toast_message(request, title: str, message: str, message_type: str = 'info'):
    """Add a toast message directly to the request object."""
    ic("add_toast_message called:", {
        'title': title,
        'message': message,
        'type': message_type
    })
    
    request.toast_message = {
        'message': message,
        'type': message_type
    }
    
    ic("Toast message added to request:", request.toast_message) 