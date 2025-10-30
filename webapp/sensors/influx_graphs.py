from datetime import datetime
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import pandas as pd

from django.utils import timezone
from icecream import ic
from influxdb_client_3 import InfluxDBClient3
from .models import Sensor
import time

from .utils import get_influxdb_client


def get_influx_sensor_data(sensor: Sensor, start_date: datetime, end_date: datetime) -> tuple[list, float]:
    """
    Queries InfluxDB for a given sensor's data within a specified time range.
    Can filter by a relative time_range or an absolute start/end time.
    """
    ic(f"Querying data for InfluxDB sensor: {sensor.name} from {start_date} to {end_date}")

    if not sensor.influx_source:
        ic("Sensor has no InfluxDB source configured.")
        return [], 0
    
    # Determine the correct filter field based on sensor's device type.
    filter_field = "dev_eui"
    device_id_val = sensor.device.device_id
    ic(f"Using filter field '{filter_field}' with value '{device_id_val}'")

    try:
        client = get_influxdb_client(sensor.influx_source)
        measurement = sensor.influx_measurement
        
        time_filter = f"time >= '{start_date.isoformat()}' AND time <= '{end_date.isoformat()}'"

        if sensor.data_type == 'INFLUX_CUMULATIVE_RESET':
            query = f"""
                WITH lagged_values AS (
                    SELECT time, "value", LAG("value", 1) OVER (ORDER BY time) as prev_value
                    FROM "{measurement}"
                    WHERE {time_filter} AND "{filter_field}" = '{device_id_val}'
                ), differences AS (
                    SELECT time, "value" - prev_value as diff
                    FROM lagged_values
                    WHERE prev_value IS NOT NULL
                )
                SELECT time, diff as "value" FROM differences WHERE diff >= 0 ORDER BY time ASC
            """
        else:
            query = f"""
                SELECT time, "value"
                FROM "{measurement}"
                WHERE {time_filter} AND "{filter_field}" = '{device_id_val}'
                ORDER BY time ASC
            """
        ic("Generated InfluxDB Query:", query)

        start_time = time.perf_counter()
        reader = client.query(query=query, language="sql")
        df = reader.to_pandas().reset_index()
        end_time = time.perf_counter()
        query_time = (end_time - start_time) * 1000
        ic(f"InfluxDB query completed in {query_time:.2f} ms, returned {len(df)} rows.")

        if df.empty:
            return [], query_time

        df['time'] = df['time'].dt.tz_localize('UTC')
        
        results = []
        decimal_places = sensor.sensor_type.decimal_places
        precision = Decimal('1e-' + str(decimal_places)) if decimal_places is not None else None

        for index, row in df.iterrows():
            if pd.notna(row['value']):
                value = Decimal(row['value'])
                if precision:
                    value = value.quantize(precision, rounding=ROUND_HALF_UP)
                results.append((row['time'], float(value)))
            else:
                results.append((row['time'], None))
                
        return results, query_time

    except Exception as e:
        ic(f"Error during InfluxDB query for sensor {sensor.name}: {e}")
        return [], 0


def get_lorawan_sensor_data(sensor: Sensor, start_date: datetime, end_date: datetime) -> tuple[list, float]:
    """
    Queries InfluxDB for a given LoRaWAN sensor's data within a specified time range.
    Can filter by a relative time_range or an absolute start/end time.
    """
    if not isinstance(sensor, Sensor) or not sensor.device.is_lorawan:
        ic("Attempted to query non-LoRaWAN sensor with get_lorawan_sensor_data")
        return [], 0
    
    return get_influx_sensor_data(sensor, start_date, end_date) 