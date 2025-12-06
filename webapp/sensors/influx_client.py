from influxdb_client_3 import InfluxDBClient3, Point
import pyarrow as pa
from django.conf import settings
from .models import InfluxStore
import logging
from icecream import ic
import time
import random

logger = logging.getLogger(__name__)

def write_sensor_reading_to_influx(sensor, value):
    """
    Finds the correct InfluxDB store for a sensor and writes a reading to it.
    """
    from .models import Place  # Local import to avoid circular dependency
    place = sensor.device.location.place

    influx_store = None
    if sensor.device.is_switchbot:
        influx_store = place.switchbot_influx_store
    else:
        # Fallback for non-switchbot devices
        influx_store = sensor.influx_store or place.default_influx_store

    if not influx_store:
        ic(f"No InfluxDB store configured for sensor {sensor.name} (PK: {sensor.pk}). Skipping write.")
        return

    # Prepare tags and fields for the write operation
    tags = {
        "device_id": sensor.device.device_id,
        "sensor_name": sensor.name,
        "place": place.slug,
        "location": sensor.device.location.slug,
    }
    # Filter out None values from tags
    tags = {k: v for k, v in tags.items() if v is not None}

    fields = {sensor.influx_field_name or 'value': value}

    try:
        write_to_influx(
            influx_store=influx_store,
            measurement=sensor.influx_measurement,
            fields=fields,
            tags=tags
        )
    except Exception as e:
        ic(f"Error writing to InfluxDB for sensor {sensor.name}: {e}")
        # Decide if you want to re-raise the exception or just log it
        # raise


def write_to_influx(influx_store: InfluxStore, measurement: str, fields: dict, tags: dict = None):
    """
    Writes a data point to InfluxDB v3.

    Args:
        influx_store (InfluxStore): The InfluxDB store to write to.
        measurement (str): The measurement name.
        fields (dict): A dictionary of field keys and values.
        tags (dict, optional): A dictionary of tags. Defaults to None.
    """
    try:
        client = get_influxdb_client(influx_store)

        point = Point(measurement)

        if tags:
            for key, value in tags.items():
                point.tag(key, value)

        for key, value in fields.items():
            if value is not None:
                point.field(key, float(value))

        client.write(database=influx_store.bucket_name, record=point)
        
        # Enhanced success log
        field_log = ", ".join([f"{k}={v}" for k, v in fields.items()])
        tag_log = ", ".join([f"{k}={v}" for k, v in tags.items()]) if tags else "No tags"
        ic(f"Success: WritePoint to measurement '{measurement}'", f"fields=[{field_log}]", f"tags=[{tag_log}]")

    except Exception as e:
        ic(f"Failed to write to InfluxDB v3 for store {influx_store.name}: {e}")
        raise
    finally:
        if 'client' in locals() and client:
            client.close()

def test_influx_bucket(url: str, token: str, org: str, bucket_name:str):
    """
    Tests the connection to an InfluxDB v3 instance by executing a simple query.

    Args:
        url (str): The InfluxDB instance URL.
        token (str): The authentication token.
        org (str): The organization name.
        bucket_name (str): The bucket/database name.

    Returns:
        tuple: A tuple containing a boolean (success), a string (message), and an int (query_time_ms).
    """
    client = None
    start_time = time.perf_counter()
    try:
        client = InfluxDBClient3(host=url, token=token, org=org, database=bucket_name)
        
        query = "SELECT 1"
        # This will raise an exception on failure.
        client.query(query=query, database=bucket_name, language="sql")
        end_time = time.perf_counter()

        query_time_ms = int((end_time - start_time) * 1000)
        message = (
            f"Connection successful.\n"
            f"Executed test query: '{query}' on bucket '{bucket_name}'."
        )
        return True, message, query_time_ms

    except Exception as e:
        end_time = time.perf_counter()
        query_time_ms = int((end_time - start_time) * 1000)
        ic(f"InfluxDB connection test failed for url {url}: {e}")
        message = (
            f"Connection to '{url}' failed after {query_time_ms}ms.\n"
            f"Bucket: '{bucket_name}'\n"
            f"Error: {e}"
        )
        return False, message, query_time_ms
    finally:
        if client:
            client.close()


# This function is deprecated and uses a v2 client pattern. It is not used anywhere.
# def test_influx_bucket_connection(url, token, org, bucket_name):
#     """
#     Tests the connection to an InfluxDB store by performing a simple query.
#     This is a generic test and does not check for specific measurements.
#     Returns a tuple: (bool: success, str: message).
#     """
#     ic(f"Testing InfluxDB store connection with URL: {url}, Org: {org}, Bucket: {bucket_name}")
#     try:
#         with get_influxdb_client_v2_compat(url=url, token=token, org=org) as client:
#             query_api = client.query_api()
#             # A simple query to check if the connection and credentials are valid
#             # and the bucket exists.
#             query = f'from(bucket: "{bucket_name}") |> range(start: -1m) |> limit(n: 1)'
#             ic("Test source query:", query)
#             result = query_api.query(query)
#             ic("Test source query result:", result)
#             # If the query executes without error, the connection is considered successful.
#             return True, "Connection successful."
#     except Exception as e:
#         ic(f"InfluxDB store connection test failed: {e}")
#         return False, f"Connection failed: {e}"


def get_influx_sensor_stats(sensor):
    """
    Connects to InfluxDB and retrieves key statistics for a specific sensor.
    """
    if not sensor.influx_store:
        return {'error': 'No InfluxDB store configured for this sensor.'}

    latest_reading_result = get_latest_influx_reading(sensor)
    
    # The user wants to see the query and the result.
    # The view will handle the logic of what to display.
    return {
        'latest_reading': latest_reading_result.get('reading') if latest_reading_result else None,
        'query': latest_reading_result.get('query') if latest_reading_result else None,
    }


def test_influx_sensor_read(sensor):
    """
    Connects to InfluxDB and retrieves key statistics for a specific sensor's measurement.
    """
    if not sensor.influx_store:
        return {'error': 'No InfluxDB store configured for this sensor.'}

    stats = {
        'record_count': get_influx_record_count(sensor),
        'latest_reading': get_latest_influx_reading(sensor),
        'earliest_reading': get_earliest_influx_reading(sensor),
    }

    # Add a check to see if any data was returned
    if stats['record_count'] == 0 and not stats['latest_reading']:
        stats['error'] = "No records found for this sensor's measurement in the store."
    
    return stats


def get_influx_record_count(sensor):
    """
    Counts the total number of records for a sensor in InfluxDB using SQL.
    """
    if not sensor.influx_store or not sensor.influx_measurement:
        return 0

    client = get_influxdb_client(sensor.influx_store)
    query = f"SELECT COUNT(*) FROM \"{sensor.influx_measurement}\""
    ic("Count source query:", query)

    try:
        reader = client.query(query=query, database=sensor.influx_store.bucket_name, language='sql')
        table = reader.read_all()
        # The result is a PyArrow Table. The count is in the first column of the first row.
        count = table.column(0)[0].as_py()
        ic("Count source query result:", count)
        return count
    except Exception as e:
        ic(f"Error getting record count from InfluxDB: {e}")
        return 0
    finally:
        if client:
            client.close()

def get_earliest_influx_reading(sensor):
    """
    Fetches the single earliest reading for a sensor from InfluxDB using SQL.
    """
    if not sensor.influx_store or not sensor.influx_measurement:
        return None

    client = get_influxdb_client(sensor.influx_store)
    field_to_select = sensor.influx_field_name or 'value'

    query = f'SELECT FIRST("{field_to_select}"), "time" FROM "{sensor.influx_measurement}"'
    ic("Earliest source query:", query)

    try:
        reader = client.query(query=query, database=sensor.influx_store.bucket_name, language='sql')
        table = reader.read_all()
        if table.num_rows > 0:
            value = table.column(0)[0].as_py()
            time = table.column(1)[0].as_py()
            earliest = {'value': value, 'time': time}
            ic("Earliest source query result:", earliest)
            return earliest
        return None
    except Exception as e:
        ic(f"Error getting earliest reading from InfluxDB: {e}")
        return None
    finally:
        if client:
            client.close()


def get_latest_influx_reading(sensor: 'Sensor'):
    """
    Fetches the single most recent reading for a sensor from InfluxDB using SQL.
    Returns a dictionary with the reading and the query string.
    """
    if not sensor.influx_store or not sensor.influx_measurement:
        return None

    client = get_influxdb_client(sensor.influx_store)
    field_to_select = sensor.influx_field_name or 'value'
    
    # Build the WHERE clause for filtering by the specific device
    tag_key = sensor.influx_tag_key or 'device_id'
    tag_value = sensor.device.device_id
    where_clause = f"WHERE \"{tag_key}\" = '{tag_value}'"

    # Using SQL for InfluxDB v3. Order by time descending and take the first one.
    query = f'SELECT "time", "{field_to_select}" FROM "{sensor.influx_measurement}" {where_clause} ORDER BY time DESC LIMIT 1'

    ic("Latest source query:", query)
    try:
        table = client.query(query=query, database=sensor.influx_store.bucket_name, language='sql')
        
        if table.num_rows > 0:
            # PyArrow table access
            time_val = table.column(0)[0].as_py()
            value = table.column(1)[0].as_py()
            # Construct a record-like object for template compatibility
            latest = {'time': time_val, field_to_select: value}
            ic("Latest source query result:", latest)
            return {'reading': latest, 'query': query}
            
        ic("Latest source query result: No records found.")
        return {'reading': None, 'query': query}

    except Exception as e:
        ic(f"Error getting latest reading from InfluxDB: {e}")
        return {'reading': None, 'query': query, 'error': str(e)}
    finally:
        if client:
            client.close()


def test_influx_write_read(store: InfluxStore):
    """
    Tests write and read functionality for an InfluxDB store.
    Writes a random value to a test measurement, reads it back immediately, and verifies.
    """
    test_measurement = "test_write"
    test_field = "random"
    test_tag_key = "tester"
    test_tag_value = "sensors_tester"
    test_value = round(random.uniform(0, 100), 1)

    record_details = {
        "bucket": store.bucket_name,
        "measurement": test_measurement,
        "tag_key": test_tag_key,
        "tag_value": test_tag_value,
        "field_name": test_field,
        "field_value": test_value
    }
    
    client = None
    try:
        client = InfluxDBClient3(host=store.url, token=store.token, org=store.org, database=store.bucket_name)
        
        # --- Write Test ---
        start_write = time.time()
        point = Point(test_measurement).tag(test_tag_key, test_tag_value).field(test_field, test_value)
        client.write(record=point)
        end_write = time.time()
        write_time_ms = int((end_write - start_write) * 1000)

        # --- Read Test (immediately after) ---
        start_read = time.time()
        query = f'SELECT * FROM "{test_measurement}" WHERE "{test_tag_key}" = \'{test_tag_value}\' ORDER BY time DESC LIMIT 1'
        ic(f"Performing read test with query: {query}")
        table = client.query(query=query, language='sql')
        end_read = time.time()
        read_time_ms = int((end_read - start_read) * 1000)

        # --- Verification ---
        if table.num_rows == 0:
            return {"success": False, "message": "Write succeeded, but no data was returned on read.", "record": record_details}

        read_value = table.to_pydict()[test_field][0]

        if read_value == test_value:
            return {
                "success": True,
                "message": f"Successfully wrote {test_value} and read it back.",
                "record": record_details,
                "write_time_ms": write_time_ms,
                "read_time_ms": read_time_ms
            }
        else:
            return {
                "success": False,
                "message": f"Value mismatch. Wrote {test_value}, but read back {read_value}.",
                "record": record_details,
                "write_time_ms": write_time_ms,
                "read_time_ms": read_time_ms
            }

    except Exception as e:
        ic(f"Error during write/read test for store {store.name}: {e}")
        return {"success": False, "message": str(e)}
    finally:
        if client:
            client.close()


def get_influxdb_client(influx_store: InfluxStore):
    """Initializes InfluxDB v3 client."""
    return InfluxDBClient3(
        host=influx_store.url,
        token=influx_store.token,
        org=influx_store.org,
        database=influx_store.bucket_name
    )

# This function raises a NotImplementedError and is not used.
# def get_influxdb_client_v2_compat(url, token, org):
#     """
#     This is a compatibility function. The V3 client can't be used for the generic
#     bucket connection test which uses Flux. For that, we need the V2 client.
#     However, since the project uses influxdb3-python, we can't have both.
#     This function needs to be removed or adapted once the test strategy is confirmed.
#     For now, it will raise an error if called.
#     """
#     raise NotImplementedError("The InfluxDB v2 compatibility client is not available with the influxdb3-python library.")
