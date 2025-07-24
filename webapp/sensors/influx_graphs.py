from influxdb_client_3 import InfluxDBClient3

def get_lorawan_sensor_data(sensor, time_range='1h'):
    """
    Queries InfluxDB for a given LoRaWAN sensor's data.
    """
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
        SELECT "value"
        FROM "{sensor.influx_measurement}"
        WHERE time > now() - interval '{time_range}'
        AND "device_id" = '{sensor.device.device_id}'
    """

    try:
        reader = client.query(query=query, language="sql")
        results = []
        for_pandas = reader.to_pandas()
        for index, row in for_pandas.iterrows():
            results.append((row['time'], row['value']))
        return results
    except Exception as e:
        print(f"Error querying InfluxDB: {e}")
        return None 