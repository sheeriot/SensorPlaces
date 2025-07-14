import base64
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime, timezone as dt_timezone
from typing import List, Optional
import numpy as np

# Use a non-interactive backend for matplotlib
matplotlib.use('Agg')


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


# def calculate_zoom(distance=0):
#     """Calculate appropriate zoom level based on distance in kilometers"""
#     if distance <= 0.4:
#         return 16
#     if distance <= 1:
#         return 15
#     if distance <= 2:
#         return 14
#     elif distance <= 4:
#         return 13
#     elif distance <= 10:
#         return 12
#     elif distance <= 17:
#         return 11
#     elif distance <= 30:
#         return 10
#     elif distance <= 60:
#         return 9
#     elif distance <= 120:
#         return 8
#     elif distance <= 250:
#         return 7
#     elif distance <= 550:
#         return 6
#     elif distance <= 1100:
#         return 5
#     elif distance <= 2000:
#         return 4
#     elif distance <= 5000:
#         return 3
#     else:
#         return 2


# def add_toast_message(request, title: str, message: str, message_type: str = 'info'):
#     """Add a toast message directly to the request object.
    
#     Args:
#         request: The request object to attach the message to
#         title: The title of the message (may be used in modal views)
#         message: The main message content
#         message_type: Type of message ('success', 'info', 'warning', 'danger')
#     """
#     # ic("add_toast_message called:", {
#     #     'title': title,
#     #     'message': message,
#     #     'type': message_type
#     # })
    
#     # Ensure message type is valid
#     valid_types = ['success', 'info', 'warning', 'danger']
#     if message_type not in valid_types:
#         message_type = 'info'
    
#     # Format the message if title is provided
#     formatted_message = f"{title}: {message}" if title else message
    
#     request.toast_message = {
#         'message': formatted_message,
#         'type': message_type,
#         'addToHistory': True  # API responses should be added to history
#     }
    
#     # ic("Toast message added to request:", request.toast_message)

# def mark_toast_as_read(request, toast_id, read_status=True):
#     """Mark a toast notification as read/unread.
    
#     Args:
#         request: The request object
#         toast_id: The ID of the toast to mark
#         read_status: Boolean indicating whether to mark as read (True) or unread (False)
    
#     Returns:
#         JsonResponse with updated unread count
#     """
#     if not request.user.is_authenticated:
#         return JsonResponse({'error': 'Authentication required'}, status=401)
    
#     try:
#         toast = ToastNotification.objects.get(id=toast_id, user=request.user)
#         toast.read = read_status
#         toast.save()
        
#         # Get updated unread count
#         unread_count = ToastNotification.objects.filter(
#             user=request.user,
#             read=False
#         ).count()
        
#         return JsonResponse({
#             'success': True,
#             'unread_count': unread_count
#         })
#     except ToastNotification.DoesNotExist:
#         return JsonResponse({'error': 'Toast not found'}, status=404)

# def clear_toast_history(request):
#     """Clear all toast notifications for the current user.
    
#     Args:
#         request: The request object
    
#     Returns:
#         JsonResponse indicating success/failure
#     """
#     if not request.user.is_authenticated:
#         return JsonResponse({'error': 'Authentication required'}, status=401)
    
#     try:
#         ToastNotification.objects.filter(user=request.user).delete()
#         return JsonResponse({'success': True})
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)


def generate_sparkline(timestamps: List[datetime]) -> Optional[str]:
    """
    Generates a sparkline chart from a list of timestamps, showing their
    distribution over time from the first reading to now.
    """
    if not timestamps or len(timestamps) < 2:
        return None

    # Ensure timestamps are timezone-aware (assuming UTC if naive)
    aware_timestamps = []
    for ts in timestamps:
        if ts.tzinfo is None:
            aware_timestamps.append(ts.replace(tzinfo=dt_timezone.utc))
        else:
            aware_timestamps.append(ts)
    
    aware_timestamps.sort()

    x_values = aware_timestamps
    # Y-axis has no meaning, use random jitter for density visualization
    y_values = np.random.uniform(0, 1, len(x_values))

    fig, ax = plt.subplots(figsize=(4, 0.4), dpi=120)
    
    # Plot the readings as dots
    ax.scatter(x_values, y_values, s=8, alpha=0.5, color='dodgerblue', edgecolor='none')

    # --- Configure Axes ---
    start_time = aware_timestamps[0]
    end_time = datetime.now(dt_timezone.utc)
    ax.set_xlim(start_time, end_time)
    ax.set_ylim(0, 1) # Set Y-lim to the data range
    
    # --- Configure Spines & Ticks for a minimal look ---
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(True)
    ax.spines['bottom'].set_color('lightgray')
    ax.spines['bottom'].set_linewidth(0.8)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.tick_params(axis='both', which='both', length=0)

    # --- Add 'first' and 'now' labels ---
    # Use axes coordinates to place text just below the bottom spine.
    ax.text(0, -0.1, 'first', ha='left', va='top', fontsize=12, color='gray', transform=ax.transAxes, clip_on=False)
    ax.text(1, -0.1, 'now', ha='right', va='top', fontsize=12, color='gray', transform=ax.transAxes, clip_on=False)
    
    # --- Save to buffer ---
    buf = BytesIO()
    plt.tight_layout(pad=0)
    plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)
    
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()

    return f"data:image/png;base64,{image_base64}"