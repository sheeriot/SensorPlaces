import logging
import os
from django.conf import settings
from datetime import datetime
from icecream import ic

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
from datetime import timezone as dt_timezone
from typing import List, Optional
import numpy as np
from influxdb_client_3 import InfluxDBClient3
from icecream import ic
import pandas as pd

# Use a non-interactive backend for matplotlib
matplotlib.use('Agg')

# --- DEBUG FLAG ---
# Set to True to bypass the stale check and always query for live values.
DISABLE_STALE_CHECK = False


def get_influxdb_client(influx_store):
    return InfluxDBClient3(
        host=influx_store.url,
        token=influx_store.token,
        org=influx_store.org,
        database=influx_store.bucket_name
    )

def get_sensor_readings(sensor, start=None, stop=None, limit=100):
    if not sensor.influx_store or sensor.data_store != 'INFLUX':
        return []

    client = get_influxdb_client(sensor.influx_store)

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
    if not sensor.influx_store or not sensor.influx_measurement:
        return None

    client = get_influxdb_client(sensor.influx_store)

    # Use the specific field name if available, otherwise default to 'value'
    field_to_select = sensor.influx_field_name or 'value'

    # Determine the correct filter field.
    if sensor.influx_tag_key:
        filter_field = sensor.influx_tag_key
    elif sensor.influx_measurement and 'frmpayload' in sensor.influx_measurement:
        filter_field = "dev_eui"
    elif sensor.device.is_lorawan:
        filter_field = "dev_eui"
    else:
        filter_field = "device_id" # Default

    device_id_val = sensor.device.device_id

    query = f'''
    SELECT *
    FROM "{sensor.influx_measurement}"
    WHERE "{filter_field}" = '{device_id_val}' AND "{field_to_select}" IS NOT NULL
    ORDER BY time DESC
    LIMIT 1
    '''

    try:
        reader = client.query(query, language="sql")
        df = reader.to_pandas()

        # This is the robust way to check for an empty DataFrame.
        if df.empty:
            return None

        latest = df.iloc[0]

        # Check for pandas NaT (Not a Time) and NaN (Not a Number)
        # Use the dynamically selected field name here
        if pd.notna(latest['time']) and pd.notna(latest[field_to_select]):
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
                'value': float(latest[field_to_select])
            }
        else:
            return None

    except Exception as e:
        ic(f"Error during InfluxDB latest reading query for sensor '{sensor.name}': {e}")
        return None
    finally:
        client.close()

def get_influx_record_count(sensor):
    """
    Counts the total number of records for a sensor in InfluxDB.
    """
    if not sensor.influx_store or not sensor.influx_measurement:
        return 0

    client = get_influxdb_client(sensor.influx_store)
    field_to_count = sensor.influx_field_name or 'value'

    # Determine the correct filter field for the WHERE clause
    if sensor.influx_tag_key:
        filter_field = sensor.influx_tag_key
    elif sensor.influx_measurement and 'frmpayload' in sensor.influx_measurement:
        filter_field = "dev_eui"
    elif sensor.device.is_lorawan:
        filter_field = "dev_eui"
    else:
        filter_field = "device_id" # Default

    device_id_val = sensor.device.device_id

    query = f'''
    SELECT count("{field_to_count}")
    FROM "{sensor.influx_measurement}"
    WHERE "{filter_field}" = '{device_id_val}' AND "{field_to_count}" IS NOT NULL AND time >= now() - interval '10 year'
    '''
    try:
        reader = client.query(query, language='sql')
        df = reader.to_pandas()
        if not df.empty:
            # Access the first column by position to be robust
            return df.iloc[0, 0]
        return 0
    except Exception as e:
        # ic(f"Error during InfluxDB count query for sensor '{sensor.name}': {e}")
        return 0
    finally:
        client.close()

def write_sensor_reading_to_influx(sensor, value):
    """
    Writes a sensor reading to the appropriate InfluxDB store if the sensor is active
    and the source is configured.
    """
    from django.utils import timezone
    if not sensor.is_active:
        return

    place = sensor.device.location.place
    influx_store = None

    if sensor.device.is_switchbot:
        influx_store = place.switchbot_influx_store
    else:
        # This logic might need refinement for non-switchbot sensors
        influx_store = sensor.influx_store or place.default_influx_store

    if not influx_store:
        return

    try:
        client = get_influxdb_client(influx_store)

        measurement_name = sensor.influx_measurement
        if not measurement_name:
            if sensor.device.is_switchbot:
                measurement_name = 'switchbot_readings'
            else:
                measurement_name = 'sensor_readings' # A sensible default

        field_name = sensor.influx_field_name or 'value'

        field_value = float(value)
        # Handle case where InfluxDB expects an integer (e.g., battery percentage)
        if sensor.sensor_type and sensor.sensor_type.name in ['Battery Level']:
            try:
                field_value = int(float(value))
            except (ValueError, TypeError):
                # If conversion fails, just use the float value and let Influx handle it
                pass

        point = {
            "measurement": measurement_name,
            "tags": {
                "device_id": str(sensor.device.device_id) if sensor.device.device_id else 'N/A',
                "sensor_id": str(sensor.id),
                "sensor_name": sensor.name,
                "sensor_type": sensor.sensor_type.name if sensor.sensor_type else 'N/A',
                "place_name": place.name,
                "location_name": sensor.device.location.name,
            },
            "fields": {field_name: field_value},
            "time": timezone.now()
        }

        client.write(record=point)
        client.close()

        # _verify_influx_write(sensor)

    except Exception as e:
        ic(f"InfluxWrite: Error writing to InfluxDB for sensor '{sensor.name}': {e}")
        error_str = str(e)
        if "table schema conflict" in error_str and "float" in error_str and "integer" in error_str:
            log_message = f"InfluxWrite Error for {sensor.name}: Data type mismatch, expected integer, received float."
            record_webhook_activity(log_message)


def _verify_influx_write(sensor):
    """
    Helper function to verify a write to InfluxDB by reading the latest value and count.
    """
    latest_reading = get_latest_influx_reading(sensor)
    record_count = get_influx_record_count(sensor)


def update_sensor_live_value(sensor, force_update=False):
    """
    Fetches and updates the live value for a single sensor. This function is the
    central point for keeping sensor data current.

    Logic:
    1. Always records the time of the check in `last_cached_timestamp`.
    2. Determines if a new value needs to be fetched from the source (e.g., API, InfluxDB)
       based on the `effective_stale_threshold` or if `force_update` is True.
    3. If a fetch is required, it queries the appropriate data source.
    4. If a new, fresher value is obtained, it updates the sensor's cached fields.
    5. All updates are performed in a single, efficient database query.
    """
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    update_kwargs = {'last_cached_timestamp': now}
    value_was_updated = False

    # Determine if it's time to fetch a new reading based on the stale threshold.
    # We check the READING timestamp (when data was actually recorded), not the check timestamp.
    time_to_fetch = True
    reading_age_str = "Never"
    stale_threshold = sensor.effective_stale_threshold

    if sensor.cached_reading_timestamp and not force_update:
        # Check how old the actual READING is, not when we last checked
        reading_age = now - sensor.cached_reading_timestamp
        reading_age_seconds = int(reading_age.total_seconds())
        reading_age_str = f"{reading_age_seconds}s"
        if reading_age < timedelta(seconds=stale_threshold):
            time_to_fetch = False
    elif not sensor.cached_reading_timestamp:
        reading_age_str = "N/A (no reading)"
        reading_age_seconds = None
    else: # force_update is True
        reading_age = now - sensor.cached_reading_timestamp
        reading_age_seconds = int(reading_age.total_seconds())
        reading_age_str = f"{reading_age_seconds}s"

    ic(f"STALE_CHECK '{sensor.name}' (pk={sensor.pk}): is_switchbot={sensor.device.is_switchbot}, reading_age={reading_age_str}, threshold={stale_threshold}s, time_to_fetch={time_to_fetch}, force={force_update}")

    if not time_to_fetch:
        ic(f"-> NOT STALE: '{sensor.name}' cache still fresh. Returning cached source='{sensor.cached_reading_source}'")
        # Still update last_cached_timestamp to reflect when we last checked
        sensor.last_cached_timestamp = now
        sensor.__class__.objects.filter(pk=sensor.pk).update(last_cached_timestamp=now)
        # If stale check passes, the source is whatever is already in the cache.
        return (False, sensor.cached_reading_source or 'cache')

    # --- If we are here, a fetch is required ---

    from .switchbot_client import get_status

    new_value = None
    new_timestamp = None
    source = "Unknown"

    if sensor.device.is_switchbot:
        source = "SwitchBot API"
        ic(f"-> STALE! Fetching from {source} for '{sensor.name}'")
        place = sensor.device.location.place
        if place.switchbot_token and place.switchbot_secret:
            try:
                from .services.switchbot_service import SwitchBotService
                service = SwitchBotService(place)
                live_value = service.get_live_reading_for_sensor(sensor)

                if live_value is not None:
                    new_value = live_value
                    new_timestamp = timezone.now()

            except Exception as e:
                ic(f"-> ERROR fetching from {source}: {e}")
        else:
            ic(f"-> SKIPPED {source}: Credentials not set for place '{place.name}'")

    elif sensor.data_store and sensor.data_store.startswith('INFLUX'):
        source = "InfluxDB"
        # ic(f"-> Fetching from {source} for {sensor.name}")
        try:
            latest_reading = get_latest_influx_reading(sensor)
            if latest_reading and latest_reading.get('value') is not None:
                new_value = latest_reading['value']
                new_timestamp = latest_reading['time']
        except Exception as e:
            ic(f"-> ERROR fetching from {source}: {e}")

    else:
        source = "Local DB"
        ic(f"-> Fetching from {source} for {sensor.name}")
        try:
            from .models import SensorReading
            latest_reading = SensorReading.objects.filter(sensor=sensor).order_by('-timestamp').first()
            if latest_reading:
                new_value = latest_reading.value
                new_timestamp = latest_reading.timestamp
        except Exception as e:
            ic(f"-> ERROR fetching from {source}: {e}")

    # If a new value was successfully fetched, add it to the update.
    if new_timestamp:
        # ic(f"-> New value received. Updating cache for {sensor.name}.")
        update_kwargs['cached_reading_value'] = new_value
        update_kwargs['cached_reading_timestamp'] = new_timestamp
        update_kwargs['cached_reading_source'] = source
        value_was_updated = True
    else:
        ic(f"-> No new value could be fetched for {sensor.name}. Not updating value.")
        # If no new value is fetched, we don't update anything and report failure.
        # The source is where we tried to fetch from.
        return (False, source)

    # For SwitchBot devices, write the newly fetched value to InfluxDB for history
    # only if the sensor's data_store is set to INFLUX.
    if sensor.device.is_switchbot and value_was_updated and sensor.data_store == 'INFLUX':
        ic(f"-> Writing SwitchBot value to InfluxDB for {sensor.name}.")
        write_sensor_reading_to_influx(sensor, new_value)


    # Update the instance for immediate use in the calling view/template
    sensor.last_cached_timestamp = now
    if value_was_updated:
        sensor.cached_reading_value = update_kwargs['cached_reading_value']
        sensor.cached_reading_timestamp = update_kwargs['cached_reading_timestamp']
        sensor.cached_reading_source = source

    # Perform a single, efficient DB update query.
    sensor.__class__.objects.filter(pk=sensor.pk).update(**update_kwargs)
    # ic(f"-> DB updated for {sensor.name} with fields: {list(update_kwargs.keys())}")

    return (value_was_updated, source)

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
