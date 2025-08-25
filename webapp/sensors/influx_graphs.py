from datetime import datetime
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import pandas as pd

from django.utils import timezone
from icecream import ic
from influxdb_client_3 import InfluxDBClient3
from .models import Sensor

from .utils import get_influxdb_client


def get_lorawan_sensor_data(sensor: Sensor, start_date: datetime, end_date: datetime) -> list:
    """
    Queries InfluxDB for a given LoRaWAN sensor's data within a specified time range.
    Can filter by a relative time_range or an absolute start/end time.

    For sensor types that represent cumulative counters that reset (e.g., 'rainfall'),
    this function calculates the non-negative difference between data points to
    show the rate of change rather than the cumulative value.
    """
    results = []
    
    if not sensor.influx_source:
        return None

    if not isinstance(sensor, Sensor) or not sensor.device.is_lorawan:
        ic("Attempted to query non-LoRaWAN sensor with get_lorawan_sensor_data")
        return []
    
    ic(f"Querying data for LoRaWAN sensor: {sensor.name} from {start_date} to {end_date}")

    try:
        client = get_influxdb_client(sensor.influx_source)
        ic(f"Successfully created InfluxDB client for source: {sensor.influx_source.name}")
        
        # Determine the measurement and field from the LoRaWANSensor model
        measurement = sensor.influx_measurement
        field = "value"

        # Define the time filter based on provided dates
        if start_date and end_date:
            time_filter = f"time >= '{start_date.isoformat()}' AND time <= '{end_date.isoformat()}'"
        else:
            time_filter = f"time >= now() - interval '7 days'" # Default to 7 days


        if sensor.data_type == 'INFLUX_CUMULATIVE_RESET':
            # --- Start of new logging block ---
            # 1. Query and log the raw, untransformed data first for debugging.
            try:
                raw_query = f"""
                    SELECT time, "value"
                    FROM "{measurement}"
                    WHERE {time_filter}
                    AND "dev_eui" = '{sensor.device.device_id}'
                    ORDER BY time ASC
                """
                ic("Querying for raw cumulative data...")
                raw_reader = client.query(query=raw_query, language="sql")
                raw_pandas = raw_reader.to_pandas().reset_index()
                ic("Raw cumulative data from InfluxDB:", raw_pandas)
            except Exception as e:
                ic(f"Error querying raw InfluxDB data for logging: {e}")
            # --- End of new logic ---

            # This SQL query calculates the non-negative rate of change for a cumulative counter.
            # It uses a Common Table Expression (CTE) with the LAG window function to get the
            # previous value and calculate the difference. It filters out negative differences
            # which typically occur when a cumulative counter resets to zero.
            query = f"""
                WITH lagged_values AS (
                    SELECT
                        time,
                        "value",
                        LAG("value", 1) OVER (ORDER BY time) as prev_value
                    FROM "{measurement}"
                    WHERE {time_filter}
                    AND "dev_eui" = '{sensor.device.device_id}'
                ),
                differences AS (
                    SELECT
                        time,
                        "value" - prev_value as diff
                    FROM lagged_values
                    WHERE prev_value IS NOT NULL
                )
                SELECT
                    time,
                    diff as "value"
                FROM differences
                WHERE diff >= 0
                ORDER BY time ASC
            """
        else:
            query = f"""
                SELECT time, "value"
                FROM "{measurement}"
                WHERE {time_filter}
                AND "dev_eui" = '{sensor.device.device_id}'
                ORDER BY time ASC
            """
        ic(query)

        try:
            reader = client.query(query=query, language="sql")
            for_pandas = reader.to_pandas().reset_index()
            for_pandas['time'] = for_pandas['time'].dt.tz_localize('UTC')

            # Use dynamic precision from SensorType
            decimal_places = sensor.sensor_type.decimal_places
            if decimal_places is not None:
                precision = Decimal('1e-' + str(decimal_places))
            else:
                precision = None # No rounding if not specified

            for index, row in for_pandas.iterrows():
                if pd.notna(row['value']):
                    value = Decimal(row['value'])
                    if precision:
                        value = value.quantize(precision, rounding=ROUND_HALF_UP)
                    results.append((row['time'], float(value)))
                else:
                    results.append((row['time'], None))

            ic("Final transformed delta data (to be sent to client):", results)
            return results
        except Exception as e:
            print(f"Error querying InfluxDB: {e}")
            return []
    except Exception as e:
        ic(f"Error creating InfluxDB client for sensor {sensor.name}: {e}")
        return []

def get_lorawan_sensor_stats(sensor: Sensor):
    """
    Queries InfluxDB for a given LoRaWAN sensor's statistics.
    """
    if not sensor.influx_source:
        return None

    client = get_influxdb_client(sensor.influx_source)
    if not client:
        ic(f"Failed to create InfluxDB client for stats query on sensor {sensor.name}")
        return None

    query = f"""
        SELECT
            COUNT("value") AS reading_count,
            MIN(time) AS first_reading,
            MAX(time) AS last_reading
        FROM "{sensor.influx_measurement}"
        WHERE "dev_eui" = '{sensor.device.device_id}'
    """
    ic("InfluxDB stats query:", query)

    try:
        reader = client.query(query=query, language="sql")
        stats_df = reader.to_pandas()
        if not stats_df.empty:
            stats = stats_df.iloc[0].to_dict()
            ic("Successfully queried InfluxDB and got stats:", stats)
            return stats
        return None
    except Exception as e:
        ic(f"Error querying InfluxDB for stats: {e}")
        return None 