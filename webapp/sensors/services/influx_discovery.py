"""
Service for discovering Measurements and Fields from InfluxDB stores.

Optimized for minimal InfluxDB queries:
- discover_all_fields(): Single batch query for all measurements and fields
- Inline last values instead of separate preview queries
"""
from typing import List, Dict, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from icecream import ic
from ..models import InfluxStore
from ..influx_client import get_influxdb_client


def _escape_sql_string(value: str) -> str:
    """
    Escape a string value for safe use in InfluxDB SQL queries.
    InfluxDB SQL uses single quotes for string literals, so we escape
    single quotes by doubling them.
    """
    if value is None:
        return ''
    return str(value).replace("'", "''")


def discover_all_fields(
    influx_store: InfluxStore,
    device_id: Optional[str] = None,
    existing_sensors: Optional[Set[Tuple[str, str]]] = None
) -> Dict[str, Any]:
    """
    Discover all measurements and fields in a single batch operation.

    This is the optimized discovery function that replaces the multi-step
    discover_measurements() + discover_fields() approach.

    Args:
        influx_store: The InfluxStore instance to query
        device_id: Optional device_id to filter by (e.g., hostname)
        existing_sensors: Set of (measurement, field) tuples already imported

    Returns:
        Dict with:
        - 'success': bool
        - 'measurements': list of measurement dicts, each containing:
            - 'name': measurement name
            - 'tag_key': the tag key used for this device
            - 'hour_count': data points in last hour
            - 'fields': list of field dicts with name, type, last_value, last_time, imported
        - 'error': str if failed
    """
    if existing_sensors is None:
        existing_sensors = set()

    client = None
    try:
        client = get_influxdb_client(influx_store)

        # Step 1: Get all measurements and fields in ONE query using JOIN
        schema_query = """
            SELECT
                t.table_name as measurement,
                c.column_name as field,
                c.data_type
            FROM information_schema.tables t
            JOIN information_schema.columns c
                ON t.table_name = c.table_name AND t.table_schema = c.table_schema
            WHERE t.table_schema = 'iox'
                AND c.column_name != 'time'
                AND c.data_type NOT LIKE '%Dictionary%'
            ORDER BY t.table_name, c.column_name
        """
        ic(f"Batch discovering all fields from {influx_store.name}")

        result = client.query(query=schema_query, database=influx_store.bucket_name, language="sql")

        if hasattr(result, 'read_all'):
            table = result.read_all()
        else:
            table = result

        # Build measurement -> fields mapping
        measurements_map = defaultdict(list)
        excluded_tables = {'public', 'information_schema', 'iox'}
        known_tags = {'host', 'hostname', 'device_id', 'device', 'machine_id', 'node'}

        if table.num_rows > 0:
            for i in range(table.num_rows):
                measurement = table.column(0)[i].as_py()
                field = table.column(1)[i].as_py()
                data_type = table.column(2)[i].as_py()

                if measurement in excluded_tables:
                    continue
                if field in known_tags:
                    continue

                # Filter out string/tag types
                data_type_str = str(data_type).lower() if data_type else ''
                if 'dictionary' in data_type_str or data_type_str in ['string', 'varchar', 'text', 'utf8']:
                    continue

                measurements_map[measurement].append({
                    'name': field,
                    'type': data_type or 'unknown',
                    'last_value': None,
                    'last_time': None,
                    'imported': (measurement, field) in existing_sensors
                })

        ic(f"Found {len(measurements_map)} measurements with fields")

        # If no device_id, return all measurements without filtering
        if not device_id:
            measurements = []
            for name, fields in sorted(measurements_map.items()):
                measurements.append({
                    'name': name,
                    'tag_key': None,
                    'hour_count': 0,
                    'fields': fields
                })
            return {
                'success': True,
                'measurements': measurements,
                'error': None
            }

        # Step 2: Find which measurements have data for this device
        # Build a single UNION ALL query to check all measurements at once
        measurements_to_check = list(measurements_map.keys())
        if not measurements_to_check:
            return {
                'success': True,
                'measurements': [],
                'error': None
            }

        # First, find the tag key for each measurement (batch approach)
        measurement_tag_keys = {}
        for measurement in measurements_to_check:
            tag_key = find_matching_tag_key(influx_store, measurement, device_id, client=client)
            if tag_key:
                measurement_tag_keys[measurement] = tag_key

        ic(f"Found tag keys for {len(measurement_tag_keys)} measurements")

        # Filter to only measurements with matching tag keys
        valid_measurements = [m for m in measurements_to_check if m in measurement_tag_keys]

        if not valid_measurements:
            return {
                'success': True,
                'measurements': [],
                'error': None
            }

        # Step 3: Get hour counts for all valid measurements in one query
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)

        # Build UNION ALL query for hour counts
        union_parts = []
        escaped_device_id = _escape_sql_string(device_id)
        for measurement in valid_measurements:
            tag_key = measurement_tag_keys[measurement]
            escaped_tag_key = _escape_sql_string(tag_key)
            union_parts.append(
                f"SELECT '{_escape_sql_string(measurement)}' as measurement, COUNT(*) as cnt "
                f"FROM \"{measurement}\" "
                f"WHERE \"{tag_key}\" = '{escaped_device_id}' AND time >= '{hour_ago.isoformat()}'"
            )

        if union_parts:
            count_query = " UNION ALL ".join(union_parts)
            ic(f"Batch count query for {len(union_parts)} measurements")

            try:
                count_result = client.query(query=count_query, database=influx_store.bucket_name, language="sql")
                if hasattr(count_result, 'read_all'):
                    count_table = count_result.read_all()
                else:
                    count_table = count_result

                hour_counts = {}
                if count_table.num_rows > 0:
                    for i in range(count_table.num_rows):
                        m_name = count_table.column(0)[i].as_py()
                        cnt = count_table.column(1)[i].as_py()
                        hour_counts[m_name] = cnt or 0
            except Exception as e:
                ic(f"Error getting batch counts: {e}")
                hour_counts = {m: 0 for m in valid_measurements}
        else:
            hour_counts = {}

        # Step 4: Get last values for all fields (batch per measurement)
        # This fetches the most recent row for each measurement
        for measurement in valid_measurements:
            tag_key = measurement_tag_keys[measurement]
            fields = measurements_map[measurement]
            field_names = [f['name'] for f in fields]

            if not field_names:
                continue

            # Get the latest row with all fields
            field_select = ', '.join([f'"{f}"' for f in field_names])
            escaped_device_id = _escape_sql_string(device_id)
            last_value_query = f'''
                SELECT time, {field_select}
                FROM "{measurement}"
                WHERE "{tag_key}" = '{escaped_device_id}'
                ORDER BY time DESC
                LIMIT 1
            '''

            try:
                lv_result = client.query(query=last_value_query, database=influx_store.bucket_name, language="sql")
                if hasattr(lv_result, 'read_all'):
                    lv_table = lv_result.read_all()
                else:
                    lv_table = lv_result

                if lv_table.num_rows > 0:
                    # Get time from first column
                    time_val = lv_table.column(0)[0].as_py()
                    time_str = time_val.isoformat() if hasattr(time_val, 'isoformat') else str(time_val)

                    # Map values to fields
                    for idx, field_info in enumerate(fields):
                        try:
                            # Column 0 is time, so field columns start at 1
                            value = lv_table.column(idx + 1)[0].as_py()
                            field_info['last_value'] = value
                            field_info['last_time'] = time_str
                        except Exception:
                            pass
            except Exception as e:
                ic(f"Error getting last values for {measurement}: {e}")

        # Build final result
        measurements = []
        for measurement in valid_measurements:
            if hour_counts.get(measurement, 0) > 0:
                measurements.append({
                    'name': measurement,
                    'tag_key': measurement_tag_keys[measurement],
                    'hour_count': hour_counts.get(measurement, 0),
                    'fields': measurements_map[measurement]
                })

        # Sort by measurement name
        measurements.sort(key=lambda x: x['name'])

        ic(f"Returning {len(measurements)} measurements with data for device {device_id}")
        return {
            'success': True,
            'measurements': measurements,
            'error': None
        }

    except Exception as e:
        ic(f"Error in batch discovery: {e}")
        return {
            'success': False,
            'measurements': [],
            'error': str(e)
        }
    finally:
        if client:
            client.close()


def get_latest_field_value(
    influx_store: InfluxStore,
    measurement: str,
    field: str,
    device_id: Optional[str] = None,
    tag_key: str = 'device_id'
) -> Dict[str, Any]:
    """
    Get the latest value for a single field. Used when creating sensors
    to populate initial cached values.

    Returns:
        Dict with 'success', 'value', 'timestamp', 'error'
    """
    client = None
    try:
        client = get_influxdb_client(influx_store)

        where_clause = ""
        if device_id:
            escaped_device_id = _escape_sql_string(device_id)
            where_clause = f'WHERE "{tag_key}" = \'{escaped_device_id}\''

        query = f'''
            SELECT time, "{field}" as value
            FROM "{measurement}"
            {where_clause}
            ORDER BY time DESC
            LIMIT 1
        '''

        result = client.query(query=query, database=influx_store.bucket_name, language="sql")

        if hasattr(result, 'read_all'):
            table = result.read_all()
        else:
            table = result

        if table.num_rows > 0:
            time_val = table.column(0)[0].as_py()
            value = table.column(1)[0].as_py()

            return {
                'success': True,
                'value': value,
                'timestamp': time_val,
                'error': None
            }

        return {
            'success': True,
            'value': None,
            'timestamp': None,
            'error': None
        }

    except Exception as e:
        ic(f"Error getting latest value for {measurement}.{field}: {e}")
        return {
            'success': False,
            'value': None,
            'timestamp': None,
            'error': str(e)
        }
    finally:
        if client:
            client.close()


def discover_measurements(influx_store: InfluxStore, device_id: Optional[str] = None, tag_key: str = 'device_id') -> Dict[str, Any]:
    """
    Query InfluxDB to discover all available measurements (tables).

    Args:
        influx_store: The InfluxStore instance to query

    Returns:
        Dict with 'success' (bool), 'measurements' (list), and 'error' (str if failed)
    """
    client = None
    try:
        client = get_influxdb_client(influx_store)

        # Query to get all measurements (tables) using information_schema
        # This is more reliable than SHOW TABLES for InfluxDB v3
        query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'iox' ORDER BY table_name"
        ic(f"Discovering measurements from {influx_store.name}: {query}")

        result = client.query(query=query, database=influx_store.bucket_name, language="sql")

        # Handle both reader and table return types
        if hasattr(result, 'read_all'):
            table = result.read_all()
        else:
            table = result

        measurements = []
        if table.num_rows > 0:
            # Get table_name column
            for i in range(table.num_rows):
                measurement_name = table.column(0)[i].as_py()
                if measurement_name and measurement_name not in ['public', 'information_schema', 'iox']:
                    measurements.append(measurement_name)

        # Filter measurements to only those with data for this device_id
        if device_id:
            filtered_measurements = []
            for measurement in measurements:
                # First, find the correct tag key for this measurement
                matching_tag_key = find_matching_tag_key(influx_store, measurement, device_id, client=client)

                if not matching_tag_key:
                    ic(f"Measurement {measurement} has no matching tag key for device_id {device_id}")
                    continue

                try:
                    # Use the discovered tag key to check for data
                    escaped_device_id = _escape_sql_string(device_id)
                    check_query = f'SELECT COUNT(*) as count FROM "{measurement}" WHERE "{matching_tag_key}" = \'{escaped_device_id}\''
                    ic(f"Checking measurement {measurement} for device_id {device_id} using tag '{matching_tag_key}': {check_query}")

                    check_result = client.query(query=check_query, database=influx_store.bucket_name, language="sql")
                    if hasattr(check_result, 'read_all'):
                        check_table = check_result.read_all()
                    else:
                        check_table = check_result

                    count = 0
                    if check_table.num_rows > 0 and check_table.num_columns > 0:
                        count = check_table.column(0)[0].as_py() if check_table.num_columns > 0 else 0

                    if count > 0:
                        # Get counts for last hour and last day
                        now = datetime.utcnow()
                        hour_ago = now - timedelta(hours=1)
                        day_ago = now - timedelta(days=1)

                        hour_query = f'SELECT COUNT(*) as count FROM "{measurement}" WHERE "{matching_tag_key}" = \'{escaped_device_id}\' AND time >= \'{hour_ago.isoformat()}\''
                        day_query = f'SELECT COUNT(*) as count FROM "{measurement}" WHERE "{matching_tag_key}" = \'{escaped_device_id}\' AND time >= \'{day_ago.isoformat()}\''

                        hour_count = 0
                        day_count = 0

                        try:
                            hour_result = client.query(query=hour_query, database=influx_store.bucket_name, language="sql")
                            if hasattr(hour_result, 'read_all'):
                                hour_table = hour_result.read_all()
                            else:
                                hour_table = hour_result
                            if hour_table.num_rows > 0 and hour_table.num_columns > 0:
                                hour_count = hour_table.column(0)[0].as_py() if hour_table.num_columns > 0 else 0
                        except Exception as e:
                            ic(f"Error getting hour count for {measurement}: {e}")

                        try:
                            day_result = client.query(query=day_query, database=influx_store.bucket_name, language="sql")
                            if hasattr(day_result, 'read_all'):
                                day_table = day_result.read_all()
                            else:
                                day_table = day_result
                            if day_table.num_rows > 0 and day_table.num_columns > 0:
                                day_count = day_table.column(0)[0].as_py() if day_table.num_columns > 0 else 0
                        except Exception as e:
                            ic(f"Error getting day count for {measurement}: {e}")

                        filtered_measurements.append({
                            'name': measurement,
                            'total_count': count,
                            'hour_count': hour_count,
                            'day_count': day_count,
                            'tag_key': matching_tag_key  # Store the tag key for later use
                        })
                    else:
                        ic(f"Measurement {measurement} has no data for device_id {device_id} with tag '{matching_tag_key}'")
                except Exception as e:
                    ic(f"Error checking measurement {measurement}: {e}")
                    # Skip measurements that error - they likely don't exist or have wrong schema

            measurements = filtered_measurements
        else:
            # Convert to dict format for consistency
            measurements = [{'name': m, 'total_count': 0, 'hour_count': 0, 'day_count': 0} for m in measurements]

        ic(f"Found {len(measurements)} measurements")
        return {
            'success': True,
            'measurements': sorted(measurements, key=lambda x: x['name']),
            'error': None
        }

    except Exception as e:
        ic(f"Error discovering measurements: {e}")
        return {
            'success': False,
            'measurements': [],
            'error': str(e)
        }
    finally:
        if client:
            client.close()


def discover_fields(influx_store: InfluxStore, measurement: str, device_id: Optional[str] = None, tag_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Query InfluxDB to discover all fields (columns) in a measurement.

    Args:
        influx_store: The InfluxStore instance to query
        measurement: The measurement name to query
        device_id: Optional device_id to filter fields by
        tag_key: Optional tag key to use for filtering (will be discovered if not provided and device_id is given)

    Returns:
        Dict with 'success' (bool), 'fields' (list of dicts with name and type), and 'error' (str if failed)
    """
    client = None
    try:
        client = get_influxdb_client(influx_store)

        # If device_id is provided but tag_key is not, discover it
        if device_id and not tag_key:
            tag_key = find_matching_tag_key(influx_store, measurement, device_id, client=client)
            if not tag_key:
                ic(f"Could not find matching tag key for measurement '{measurement}' with device_id '{device_id}'")
                # Continue anyway, but filtering won't work

        # Use information_schema.columns - deterministic, standard SQL approach
        # This is the same approach we use for measurements discovery
        query = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'iox' AND table_name = '{measurement}' ORDER BY column_name"
        ic(f"Discovering fields for measurement '{measurement}': {query}")

        result = client.query(query=query, database=influx_store.bucket_name, language="sql")

        # Handle both reader and table return types
        if hasattr(result, 'read_all'):
            table = result.read_all()
        else:
            table = result

        fields = []
        if table.num_rows > 0:
            for i in range(table.num_rows):
                column_name = table.column(0)[i].as_py() if table.num_columns > 0 else None
                data_type = table.column(1)[i].as_py() if table.num_columns > 1 else None

                ic(f"Column {i}: name={column_name}, type={data_type}")

                if column_name and column_name != 'time':
                    # Filter out tag columns by data type
                    data_type_str = str(data_type).lower() if data_type else ''
                    is_tag = 'tag' in data_type_str or data_type_str in ['string', 'varchar', 'text']

                    # Also filter out known tag column names
                    known_tags = ['host', 'hostname', 'device_id', 'device', 'machine_id', 'node']

                    if not is_tag and column_name not in known_tags:
                        field_info = {
                            'name': column_name,
                            'type': data_type or 'unknown',
                            'hour_count': 0,
                            'day_count': 0
                        }

                        # If device_id is provided, check counts for this field
                        if device_id and tag_key:
                            now = datetime.utcnow()
                            hour_ago = now - timedelta(hours=1)
                            day_ago = now - timedelta(days=1)
                            escaped_device_id = _escape_sql_string(device_id)

                            try:
                                # Check last hour - COUNT(column_name) counts non-null values
                                hour_query = f'SELECT COUNT("{column_name}") as count FROM "{measurement}" WHERE "{tag_key}" = \'{escaped_device_id}\' AND time >= \'{hour_ago.isoformat()}\''
                                ic(f"Hour count query for {column_name}: {hour_query}")
                                hour_result = client.query(query=hour_query, database=influx_store.bucket_name, language="sql")
                                if hasattr(hour_result, 'read_all'):
                                    hour_table = hour_result.read_all()
                                else:
                                    hour_table = hour_result
                                if hour_table.num_rows > 0 and hour_table.num_columns > 0:
                                    hour_count = hour_table.column(0)[0].as_py() if hour_table.num_columns > 0 else 0
                                    field_info['hour_count'] = hour_count
                                    ic(f"Hour count for {column_name}: {hour_count}")
                            except Exception as e:
                                ic(f"Error getting hour count for field {column_name} in {measurement}: {e}")

                            try:
                                # Check last day
                                day_query = f'SELECT COUNT("{column_name}") as count FROM "{measurement}" WHERE "{tag_key}" = \'{escaped_device_id}\' AND time >= \'{day_ago.isoformat()}\''
                                ic(f"Day count query for {column_name}: {day_query}")
                                day_result = client.query(query=day_query, database=influx_store.bucket_name, language="sql")
                                if hasattr(day_result, 'read_all'):
                                    day_table = day_result.read_all()
                                else:
                                    day_table = day_result
                                if day_table.num_rows > 0 and day_table.num_columns > 0:
                                    day_count = day_table.column(0)[0].as_py() if day_table.num_columns > 0 else 0
                                    field_info['day_count'] = day_count
                                    ic(f"Day count for {column_name}: {day_count}")
                            except Exception as e:
                                ic(f"Error getting day count for field {column_name} in {measurement}: {e}")

                        fields.append(field_info)

        ic(f"Found {len(fields)} fields in measurement '{measurement}'")
        return {
            'success': True,
            'fields': fields,
            'error': None
        }

    except Exception as e:
        ic(f"Error discovering fields for measurement '{measurement}': {e}")
        return {
            'success': False,
            'fields': [],
            'error': str(e)
        }
    finally:
        if client:
            client.close()


def preview_measurement_field(
    influx_store: InfluxStore,
    measurement: str,
    field: str,
    device_id: Optional[str] = None,
    tag_key: str = 'device_id',
    limit: int = 10
) -> Dict[str, Any]:
    """
    Preview sample data for a measurement+field combination.

    Args:
        influx_store: The InfluxStore instance to query
        measurement: The measurement name
        field: The field name to preview
        device_id: Optional device_id to filter by tag
        tag_key: The tag key to use for filtering (default: 'device_id')
        limit: Number of samples to return (default: 10)

    Returns:
        Dict with 'success' (bool), 'samples' (list), and 'error' (str if failed)
    """
    client = None
    try:
        client = get_influxdb_client(influx_store)

        # Build WHERE clause if device_id is provided
        where_clause = ""
        if device_id:
            escaped_device_id = _escape_sql_string(device_id)
            where_clause = f'WHERE "{tag_key}" = \'{escaped_device_id}\''

        query = f'''
            SELECT time, "{field}" as value
            FROM "{measurement}"
            {where_clause}
            ORDER BY time DESC
            LIMIT {limit}
        '''
        ic(f"Previewing field '{field}' from measurement '{measurement}': {query}")

        result = client.query(query=query, database=influx_store.bucket_name, language="sql")

        # Handle both reader and table return types
        if hasattr(result, 'read_all'):
            table = result.read_all()
        else:
            table = result

        samples = []
        if table.num_rows > 0:
            for i in range(table.num_rows):
                time_val = table.column(0)[i].as_py() if table.num_columns > 0 else None
                value = table.column(1)[i].as_py() if table.num_columns > 1 else None

                if time_val is not None and value is not None:
                    samples.append({
                        'time': time_val.isoformat() if hasattr(time_val, 'isoformat') else str(time_val),
                        'value': value
                    })

        ic(f"Retrieved {len(samples)} preview samples")
        return {
            'success': True,
            'samples': samples,
            'error': None
        }

    except Exception as e:
        ic(f"Error previewing field '{field}' from measurement '{measurement}': {e}")
        return {
            'success': False,
            'samples': [],
            'error': str(e)
        }
    finally:
        if client:
            client.close()


def find_matching_tag_key(influx_store: InfluxStore, measurement: str, device_id: str, client=None) -> Optional[str]:
    """
    Find the tag key in a measurement that matches the device_id value.
    Tries common tag keys like 'host', 'device_id', 'device', etc.

    Returns the tag key if found, None otherwise.
    """
    if client is None:
        client = get_influxdb_client(influx_store)
        should_close = True
    else:
        should_close = False

    try:
        # Common tag keys to try
        tag_keys_to_try = ['host', 'device_id', 'device', 'hostname', 'machine_id', 'node']

        escaped_device_id = _escape_sql_string(device_id)
        for tag_key in tag_keys_to_try:
            try:
                # Try to query with this tag key
                test_query = f'SELECT COUNT(*) as count FROM "{measurement}" WHERE "{tag_key}" = \'{escaped_device_id}\' LIMIT 1'
                result = client.query(query=test_query, database=influx_store.bucket_name, language="sql")

                if hasattr(result, 'read_all'):
                    table = result.read_all()
                else:
                    table = result

                if table.num_rows > 0:
                    count = table.column(0)[0].as_py() if table.num_columns > 0 else 0
                    if count > 0:
                        ic(f"Found matching tag key '{tag_key}' for measurement '{measurement}' with device_id '{device_id}'")
                        return tag_key
            except Exception as e:
                # This tag key doesn't exist or doesn't match, try next
                continue

        # If none of the common keys work, try to discover tags from a sample row
        try:
            sample_query = f'SELECT * FROM "{measurement}" LIMIT 1'
            result = client.query(query=sample_query, database=influx_store.bucket_name, language="sql")

            if hasattr(result, 'read_all'):
                table = result.read_all()
            else:
                table = result

            if table.num_rows > 0:
                # Check each column to see if it matches device_id
                for i in range(table.num_columns):
                    col_name = table.column(i).name
                    if col_name and col_name != 'time':
                        try:
                            sample_value = table.column(i)[0].as_py()
                            # If it's a string and matches device_id, this might be our tag
                            if isinstance(sample_value, str) and sample_value == device_id:
                                ic(f"Found matching tag key '{col_name}' for measurement '{measurement}' by value match")
                                return col_name
                        except:
                            continue
        except:
            pass

        return None
    finally:
        if should_close and client:
            client.close()


def discover_tags(influx_store: InfluxStore, measurement: str) -> Dict[str, Any]:
    """
    Discover available tag keys in a measurement.
    This helps determine which tag key to use for filtering by device_id.

    Args:
        influx_store: The InfluxStore instance to query
        measurement: The measurement name to query

    Returns:
        Dict with 'success' (bool), 'tags' (list), and 'error' (str if failed)
    """
    client = None
    try:
        client = get_influxdb_client(influx_store)

        # Try to get tag information by querying a sample row
        query = f'SELECT * FROM "{measurement}" LIMIT 1'
        ic(f"Discovering tags for measurement '{measurement}': {query}")

        result = client.query(query=query, database=influx_store.bucket_name, language="sql")

        # Handle both reader and table return types
        if hasattr(result, 'read_all'):
            table = result.read_all()
        else:
            table = result

        tags = []
        if table.num_rows > 0 and table.num_columns > 0:
            # Get column names - tags are typically non-numeric columns (except time)
            for i in range(table.num_columns):
                column_name = table.column(i).name
                if column_name and column_name != 'time':
                    # Check if it's likely a tag (string type) vs field (numeric)
                    sample_value = table.column(i)[0].as_py() if table.num_rows > 0 else None
                    if sample_value is not None:
                        # If it's a string, it's likely a tag
                        if isinstance(sample_value, str):
                            tags.append(column_name)

        ic(f"Found {len(tags)} potential tag keys in measurement '{measurement}'")
        return {
            'success': True,
            'tags': tags,
            'error': None
        }

    except Exception as e:
        ic(f"Error discovering tags for measurement '{measurement}': {e}")
        return {
            'success': False,
            'tags': [],
            'error': str(e)
        }
    finally:
        if client:
            client.close()
