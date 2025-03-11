from influxdb_client_3 import InfluxDBClient3 as InfluxDBClient
# from django.conf import settings
# from datetime import datetime
# from django.utils.safestring import mark_safe
from icecream import ic
from django.http import JsonResponse
from .models import ToastNotification

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
    """Add a toast message directly to the request object.
    
    Args:
        request: The request object to attach the message to
        title: The title of the message (may be used in modal views)
        message: The main message content
        message_type: Type of message ('success', 'info', 'warning', 'danger')
    """
    ic("add_toast_message called:", {
        'title': title,
        'message': message,
        'type': message_type
    })
    
    # Ensure message type is valid
    valid_types = ['success', 'info', 'warning', 'danger']
    if message_type not in valid_types:
        message_type = 'info'
    
    # Format the message if title is provided
    formatted_message = f"{title}: {message}" if title else message
    
    request.toast_message = {
        'message': formatted_message,
        'type': message_type,
        'addToHistory': True  # API responses should be added to history
    }
    
    ic("Toast message added to request:", request.toast_message)

def mark_toast_as_read(request, toast_id, read_status=True):
    """Mark a toast notification as read/unread.
    
    Args:
        request: The request object
        toast_id: The ID of the toast to mark
        read_status: Boolean indicating whether to mark as read (True) or unread (False)
    
    Returns:
        JsonResponse with updated unread count
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        toast = ToastNotification.objects.get(id=toast_id, user=request.user)
        toast.read = read_status
        toast.save()
        
        # Get updated unread count
        unread_count = ToastNotification.objects.filter(
            user=request.user,
            read=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'unread_count': unread_count
        })
    except ToastNotification.DoesNotExist:
        return JsonResponse({'error': 'Toast not found'}, status=404)

def clear_toast_history(request):
    """Clear all toast notifications for the current user.
    
    Args:
        request: The request object
    
    Returns:
        JsonResponse indicating success/failure
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        ToastNotification.objects.filter(user=request.user).delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)