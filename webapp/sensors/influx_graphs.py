from influxdb_client_3 import InfluxDBClient3
from icecream import ic

def get_lorawan_sensor_data(sensor, time_range='1h'):
    """
    Queries InfluxDB for a given LoRaWAN sensor's data.
    """
    influx_source = sensor.influx_source
    if not all([influx_source, influx_source.url, influx_source.token, influx_source.org, influx_source.bucket_name, sensor.influx_measurement]):
        ic("Missing InfluxDB source details for sensor:", sensor)
        return None

    client = InfluxDBClient3(
        host=influx_source.url,
        token=influx_source.token,
        org=influx_source.org,
        database=influx_source.bucket_name
    )

    query = f"""
        SELECT time, "value"
        FROM "{sensor.influx_measurement}"
        WHERE time > now() - interval '{time_range}'
        AND "dev_eui" = '{sensor.device.device_id}'
        ORDER BY time ASC
    """

    try:
        reader = client.query(query=query, language="sql")
        results = []
        for_pandas = reader.to_pandas().reset_index()
        for_pandas['time'] = for_pandas['time'].dt.tz_localize('UTC')
        for index, row in for_pandas.iterrows():
            results.append((row['time'], row['value']))
        return results
    except Exception as e:
        print(f"Error querying InfluxDB: {e}")
        return None

def get_lorawan_sensor_stats(sensor):
    """
    Queries InfluxDB for a given LoRaWAN sensor's statistics.
    """
    if not sensor.influx_source:
        return None
    influx_source = sensor.influx_source
    if not all([influx_source, influx_source.url, influx_source.token, influx_source.org, influx_source.bucket_name, sensor.influx_measurement]):
        return None

    client = InfluxDBClient3(
        host=influx_source.url,
        token=influx_source.token,
        org=influx_source.org,
        database=influx_source.bucket_name
    )

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