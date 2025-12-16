# Migration 003: Transform legacy data to new standardized IDs
#
# This migration:
# 1. Reads alias mappings from YAML files (single source of truth)
# 2. Looks up each legacy_*_name and finds the matching new record
# 3. Sets the FK to point to the new record
# 4. Reports each transformation and any NOT FOUND items

import os
import yaml
from django.db import migrations


def get_fixtures_path():
    """Get the path to the fixtures directory."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fixtures')


def load_yaml_file(filename):
    """Load data from a YAML file in the fixtures directory."""
    filepath = os.path.join(get_fixtures_path(), filename)
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)


def build_alias_map(yaml_data, key):
    """
    Build a mapping from alias (lowercase) -> canonical name.
    Reads from YAML files which are the SINGLE SOURCE OF TRUTH.
    """
    alias_map = {}
    items = yaml_data.get(key, [])
    for item in items:
        canonical_name = item['name']
        # Map the canonical name to itself
        alias_map[canonical_name.lower()] = canonical_name
        # Map all aliases to the canonical name
        for alias in item.get('aliases', []):
            alias_map[alias.lower()] = canonical_name
    return alias_map


def build_removed_units_set():
    """
    Build a set of unit names that were intentionally removed.
    These should map to NULL (no unit).
    """
    return {
        'kelvin', 'k',
        'none', '(none)',
        'bytes', 'b', 'megabytes', 'mb', 'gigabytes', 'gb',
    }


def transform_data(apps, schema_editor):
    """Transform legacy FK references to new standardized IDs."""
    Sensor = apps.get_model('sensors', 'Sensor')
    Device = apps.get_model('sensors', 'Device')
    SensorType = apps.get_model('sensors', 'SensorType')
    Unit = apps.get_model('sensors', 'Unit')
    DeviceType = apps.get_model('sensors', 'DeviceType')

    # Load alias mappings from YAML files (single source of truth)
    units_yaml = load_yaml_file('units.yaml')
    device_types_yaml = load_yaml_file('device_types.yaml')
    sensor_types_yaml = load_yaml_file('sensor_types.yaml')

    unit_alias_map = build_alias_map(units_yaml, 'units')
    device_type_alias_map = build_alias_map(device_types_yaml, 'device_types')
    sensor_type_alias_map = build_alias_map(sensor_types_yaml, 'sensor_types')
    removed_units = build_removed_units_set()

    # Build lookup dictionaries by name (case-insensitive) from DB
    units_by_name = {u.name.lower(): u for u in Unit.objects.all()}
    device_types_by_name = {dt.name.lower(): dt for dt in DeviceType.objects.all()}
    sensor_types_by_name = {st.name.lower(): st for st in SensorType.objects.all()}

    not_found = {'units': set(), 'device_types': set(), 'sensor_types': set()}

    # --- Transform Sensors ---
    print("\n  === Transforming Sensors ===")
    for sensor in Sensor.objects.all():
        changes = []

        # Transform unit
        if sensor.legacy_unit_name:
            legacy_name_lower = sensor.legacy_unit_name.lower().strip()

            if legacy_name_lower in removed_units:
                # Intentionally removed unit - set to NULL
                sensor.unit_id = None
                changes.append(f"unit: '{sensor.legacy_unit_name}' -> NULL (removed)")
            elif legacy_name_lower in unit_alias_map:
                canonical_name = unit_alias_map[legacy_name_lower]
                if canonical_name.lower() in units_by_name:
                    new_unit = units_by_name[canonical_name.lower()]
                    sensor.unit_id = new_unit.id
                    changes.append(f"unit: '{sensor.legacy_unit_name}' (id={sensor.legacy_unit_id}) -> '{new_unit.name}' (id={new_unit.id})")
                else:
                    not_found['units'].add(sensor.legacy_unit_name)
                    changes.append(f"unit: '{sensor.legacy_unit_name}' -> NOT FOUND")
            else:
                not_found['units'].add(sensor.legacy_unit_name)
                changes.append(f"unit: '{sensor.legacy_unit_name}' -> NOT FOUND (no alias)")

        # Transform sensor_type
        if sensor.legacy_sensor_type_name:
            legacy_name_lower = sensor.legacy_sensor_type_name.lower().strip()

            if legacy_name_lower in sensor_type_alias_map:
                canonical_name = sensor_type_alias_map[legacy_name_lower]
                if canonical_name.lower() in sensor_types_by_name:
                    new_st = sensor_types_by_name[canonical_name.lower()]
                    sensor.sensor_type_id = new_st.id
                    changes.append(f"sensor_type: '{sensor.legacy_sensor_type_name}' (id={sensor.legacy_sensor_type_id}) -> '{new_st.name}' (id={new_st.id})")
                else:
                    not_found['sensor_types'].add(sensor.legacy_sensor_type_name)
                    changes.append(f"sensor_type: '{sensor.legacy_sensor_type_name}' -> NOT FOUND")
            else:
                not_found['sensor_types'].add(sensor.legacy_sensor_type_name)
                changes.append(f"sensor_type: '{sensor.legacy_sensor_type_name}' -> NOT FOUND (no alias)")

        if changes:
            sensor.save(update_fields=['unit_id', 'sensor_type_id'])
            print(f"    Sensor '{sensor.name}' (id={sensor.id}): {', '.join(changes)}")

    # --- Transform Devices ---
    print("\n  === Transforming Devices ===")
    for device in Device.objects.all():
        changes = []

        if device.legacy_device_type_name:
            legacy_name_lower = device.legacy_device_type_name.lower().strip()

            if legacy_name_lower in device_type_alias_map:
                canonical_name = device_type_alias_map[legacy_name_lower]
                if canonical_name.lower() in device_types_by_name:
                    new_dt = device_types_by_name[canonical_name.lower()]
                    device.device_type_id = new_dt.id
                    changes.append(f"device_type: '{device.legacy_device_type_name}' (id={device.legacy_device_type_id}) -> '{new_dt.name}' (id={new_dt.id})")
                else:
                    not_found['device_types'].add(device.legacy_device_type_name)
                    changes.append(f"device_type: '{device.legacy_device_type_name}' -> NOT FOUND")
            else:
                not_found['device_types'].add(device.legacy_device_type_name)
                changes.append(f"device_type: '{device.legacy_device_type_name}' -> NOT FOUND (no alias)")

        if changes:
            device.save(update_fields=['device_type_id'])
            print(f"    Device '{device.name}' (id={device.id}): {', '.join(changes)}")

    # --- Transform SensorTypes (unit_id) ---
    print("\n  === Transforming SensorTypes ===")
    for st in SensorType.objects.all():
        changes = []

        if st.legacy_unit_name:
            legacy_name_lower = st.legacy_unit_name.lower().strip()

            if legacy_name_lower in removed_units:
                st.unit_id = None
                changes.append(f"unit: '{st.legacy_unit_name}' -> NULL (removed)")
            elif legacy_name_lower in unit_alias_map:
                canonical_name = unit_alias_map[legacy_name_lower]
                if canonical_name.lower() in units_by_name:
                    new_unit = units_by_name[canonical_name.lower()]
                    st.unit_id = new_unit.id
                    changes.append(f"unit: '{st.legacy_unit_name}' (id={st.legacy_unit_id}) -> '{new_unit.name}' (id={new_unit.id})")
                else:
                    not_found['units'].add(st.legacy_unit_name)
                    changes.append(f"unit: '{st.legacy_unit_name}' -> NOT FOUND")
            else:
                not_found['units'].add(st.legacy_unit_name)
                changes.append(f"unit: '{st.legacy_unit_name}' -> NOT FOUND (no alias)")

        if changes:
            st.save(update_fields=['unit_id'])
            print(f"    SensorType '{st.name}' (id={st.id}): {', '.join(changes)}")

    # --- Report NOT FOUND items ---
    print("\n  === NOT FOUND Summary ===")
    if not_found['units']:
        print(f"    Units NOT FOUND: {', '.join(sorted(not_found['units']))}")
    if not_found['device_types']:
        print(f"    DeviceTypes NOT FOUND: {', '.join(sorted(not_found['device_types']))}")
    if not_found['sensor_types']:
        print(f"    SensorTypes NOT FOUND: {', '.join(sorted(not_found['sensor_types']))}")
    if not any(not_found.values()):
        print("    All legacy items successfully mapped!")


def reverse_transform(apps, schema_editor):
    """Reverse: restore FK values from legacy fields."""
    Sensor = apps.get_model('sensors', 'Sensor')
    Device = apps.get_model('sensors', 'Device')
    SensorType = apps.get_model('sensors', 'SensorType')

    for sensor in Sensor.objects.all():
        sensor.unit_id = sensor.legacy_unit_id
        sensor.sensor_type_id = sensor.legacy_sensor_type_id
        sensor.save(update_fields=['unit_id', 'sensor_type_id'])

    for device in Device.objects.all():
        device.device_type_id = device.legacy_device_type_id
        device.save(update_fields=['device_type_id'])

    for st in SensorType.objects.all():
        st.unit_id = st.legacy_unit_id
        st.save(update_fields=['unit_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0002_seed_data'),
    ]

    operations = [
        migrations.RunPython(transform_data, reverse_code=reverse_transform),
    ]
