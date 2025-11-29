import logging
import os
from django.conf import settings

logger = logging.getLogger(__name__)

# --- Webhook Activity Recording ---
LOGS_DIR = os.path.join(settings.BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)
WEBHOOK_RECORD_FILE = os.path.join(LOGS_DIR, 'WEBHOOK_ACTIVITY.log')

def record_webhook_activity(message: str):
    """Appends a message to the webhook activity log file if WEBHOOK_SNIFFER is True."""
    if settings.WEBHOOK_SNIFFER:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        try:
            with open(WEBHOOK_RECORD_FILE, 'a') as f:
                f.write(f"{now_str} | {message}\n")
        except Exception as e:
            logger.error(f"Failed to write to webhook record file: {e}")
# --- End of Webhook Activity Recording ---

import base64
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime, timezone as dt_timezone
from typing import List, Optional
import numpy as np
from influxdb_client_3 import InfluxDBClient3
from icecream import ic
import pandas as pd

# Use a non-interactive backend for matplotlib
matplotlib.use('Agg')

# --- DEBUG FLAG ---
# Set to True to bypass the stale check and always query for live values.
# DISABLE_STALE_CHECK = True


def get_influxdb_client(influx_source):
    return InfluxDBClient3(
        host=influx_source.url,
        token=influx_source.token,
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


def get_latest_influx_reading(sensor):
    """
    Fetches the single most recent reading for a sensor from InfluxDB.
    """
    if not sensor.influx_source or not sensor.influx_measurement:
        return None

    client = get_influxdb_client(sensor.influx_source)

    # Determine the correct filter field. If 'frmpayload' is in the measurement name,
    # it's very likely LoRaWAN data and should use 'dev_eui'.
    if 'frmpayload' in sensor.influx_measurement:
        filter_field = "dev_eui"
    else:
        # Fallback to the original logic for other measurement types
        filter_field = "dev_eui" if sensor.device.is_lorawan else "device_id"

    device_id_val = sensor.device.device_id

    query = f'''
    SELECT *
    FROM "{sensor.influx_measurement}"
    WHERE "{filter_field}" = '{device_id_val}'
    ORDER BY time DESC
    LIMIT 1
    '''

    # ic(f"Querying InfluxDB for latest reading for sensor '{sensor.name}' (pk={sensor.pk}) with query: {query}")

    try:
        reader = client.query(query, language="sql")
        df = reader.to_pandas()
        # ic("Raw response from InfluxDB:", df)

        # This is the robust way to check for an empty DataFrame.
        if df.empty:
            # ic("InfluxDB query returned no data.")
            return None

        latest = df.iloc[0]
        # ic("Latest row from DataFrame:", latest)

        # Check for pandas NaT (Not a Time) and NaN (Not a Number)
        if pd.notna(latest['time']) and pd.notna(latest['value']):
            # Convert to Python native types before returning
            # Fix UserWarning about nanoseconds by flooring to microseconds
            ts = latest['time']
            if hasattr(ts, 'floor'):
                 ts = ts.floor('us')
            py_time = ts.to_pydatetime()

            # Ensure the datetime is timezone-aware (assume UTC).
            if py_time.tzinfo is None:
                py_time = py_time.replace(tzinfo=dt_timezone.utc)

            return {
                'time': py_time,
                'value': float(latest['value'])
            }
        else:
            # ic("InfluxDB returned a row with null time or value.")
            return None

    except Exception as e:
        ic(f"Error during InfluxDB latest reading query for sensor '{sensor.name}': {e}")
        return None
    finally:
        client.close()


def update_sensor_live_value(sensor):
    """
    Fetches and updates the live value for a single sensor if it's time to check.
    This function now uses `last_checked_timestamp` to determine if a check is needed,
    preventing excessive queries for sensors that update infrequently.
    Returns True if a new value was fetched and saved, False otherwise.
    """
    from django.utils import timezone
    from datetime import timedelta

    # Decide if it's time to check based on the stale threshold.
    if 'DISABLE_STALE_CHECK' in globals() and globals()['DISABLE_STALE_CHECK']:
        pass # Skip the check if the debug flag is set
    elif sensor.last_checked_timestamp:
        time_since_last_check = timezone.now() - sensor.last_checked_timestamp
        if time_since_last_check < timedelta(seconds=sensor.effective_stale_threshold):
            return False  # Not time to check yet.

    # Proceed with the check.
    from .switchbot_client import get_status

    new_value = None
    new_timestamp = None

    if sensor.effective_data_type and sensor.effective_data_type.startswith('INFLUX'):
        try:
            latest_reading = get_latest_influx_reading(sensor)
            if latest_reading and latest_reading.get('value') is not None:
                new_value = latest_reading['value']
                new_timestamp = latest_reading['time']
        except Exception:
            pass  # Errors are logged in get_latest_influx_reading

    elif sensor.device.is_switchbot:
        try:
            status_data = get_status(sensor.device.device_id)
            if status_data.get('statusCode') == 100:
                live_body = status_data.get('body', {})
                live_values = {k.lower(): v for k, v in live_body.items()}

                if sensor.sensor_type and sensor.sensor_type.name.lower() in live_values:
                    live_value = live_values[sensor.sensor_type.name.lower()]
                    if live_value is not None:
                        new_value = live_value
                        new_timestamp = timezone.now()
        except Exception:
            pass

    else:
        # Fallback for DIRECT or other types: check local DB for the latest reading
        try:
            # Import locally to avoid circular import
            from .models import SensorReading
            latest_reading = SensorReading.objects.filter(sensor=sensor).order_by('-timestamp').first()
            if latest_reading:
                ic(f"Found local reading for sensor {sensor.name}: {latest_reading.value} at {latest_reading.timestamp}")
                new_value = latest_reading.value
                new_timestamp = latest_reading.timestamp
            else:
                ic(f"No local reading found for sensor {sensor.name}")
        except Exception as e:
            ic(f"Error getting local reading for sensor {sensor.name}: {e}")
            pass



    # --- Update the sensor object ---

    # Always update the last_checked time
    # Use .update() to bypass the full_clean() called in Sensor.save()
    # This prevents validation errors from blocking live value updates

    update_kwargs = {
        'last_checked_timestamp': timezone.now()
    }

    value_was_updated = False
    # Only update the cached value if the new reading is actually newer
    if new_timestamp and (sensor.cached_reading_timestamp is None or new_timestamp > sensor.cached_reading_timestamp):
        update_kwargs['cached_reading_value'] = new_value
        update_kwargs['cached_reading_timestamp'] = new_timestamp

        # Update the instance as well (though refresh_from_db in view would catch it)
        sensor.cached_reading_value = new_value
        sensor.cached_reading_timestamp = new_timestamp
        value_was_updated = True

    sensor.last_checked_timestamp = update_kwargs['last_checked_timestamp']
    sensor.__class__.objects.filter(pk=sensor.pk).update(**update_kwargs)

    return value_was_updated


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
