from influxdb_client_3 import InfluxDBClient3, Point
from django.conf import settings
from .models import InfluxSource
import logging

logger = logging.getLogger(__name__)

def write_to_influx(influx_source: InfluxSource, measurement: str, fields: dict, tags: dict = None):
    """
    Writes a data point to InfluxDB v3.

    Args:
        influx_source (InfluxSource): The InfluxDB source to write to.
        measurement (str): The measurement name.
        fields (dict): A dictionary of field keys and values.
        tags (dict, optional): A dictionary of tags. Defaults to None.
    """
    try:
        # For InfluxDB v3, the token is part of the client initialization,
        # and the bucket is specified during the write.
        client = InfluxDBClient3(host=influx_source.url, token=influx_source.token, org=influx_source.org, database=influx_source.bucket_name)

        point = Point(measurement)

        if tags:
            for key, value in tags.items():
                point.tag(key, value)

        for key, value in fields.items():
            # Ensure values are of a type that the client can handle, e.g., float, int, str, bool
            if value is not None:
                point.field(key, value)

        client.write(point)
        logger.info(f"Successfully wrote to InfluxDB measurement '{measurement}' in database '{influx_source.bucket_name}'.")

    except Exception as e:
        logger.error(f"Failed to write to InfluxDB v3 for source {influx_source.name}: {e}")
        raise
    finally:
        if 'client' in locals():
            client.close()
