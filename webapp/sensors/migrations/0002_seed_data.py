# Migration 002: Add legacy fields, clear tables, seed from YAML
#
# This migration:
# 1. Adds legacy_*_id and legacy_*_name fields to preserve old FK values AND names
# 2. Adds aliases (JSONField) and is_system (BooleanField) fields
# 3. Copies current FK values and names to legacy fields
# 4. Clears FK fields (sets to null)
# 5. Deletes all existing Unit, DeviceType, SensorType records
# 6. Seeds new standardized data from YAML files (source of truth)
#    - Includes aliases for auto-matching
#    - Sets is_system=True for seeded records (immutable)
#
# PK ranges after seeding:
#   - System seed data: pk < 100 (is_system=True, immutable)
#   - User-created data: pk >= 100 and < 1000
#   - Auto-created data (by webhooks/APIs): pk >= 1000

import os
import yaml
from django.db import migrations, models, connection


def get_fixtures_path():
    """Get the path to the fixtures directory."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fixtures')


def load_yaml_file(filename):
    """Load data from a YAML file in the fixtures directory."""
    filepath = os.path.join(get_fixtures_path(), filename)
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)


def copy_fks_to_legacy(apps, schema_editor):
    """Copy current FK values AND names to legacy fields before we clear them."""
    Sensor = apps.get_model('sensors', 'Sensor')
    Device = apps.get_model('sensors', 'Device')
    SensorType = apps.get_model('sensors', 'SensorType')
    Unit = apps.get_model('sensors', 'Unit')
    DeviceType = apps.get_model('sensors', 'DeviceType')

    # Build lookup dictionaries for names
    unit_names = {u.id: u.name for u in Unit.objects.all()}
    device_type_names = {dt.id: dt.name for dt in DeviceType.objects.all()}
    sensor_type_names = {st.id: st.name for st in SensorType.objects.all()}

    # Copy Sensor FK values and names to legacy fields
    for sensor in Sensor.objects.all():
        sensor.legacy_unit_id = sensor.unit_id
        sensor.legacy_unit_name = unit_names.get(sensor.unit_id, '') if sensor.unit_id else ''
        sensor.legacy_sensor_type_id = sensor.sensor_type_id
        sensor.legacy_sensor_type_name = sensor_type_names.get(sensor.sensor_type_id, '') if sensor.sensor_type_id else ''
        sensor.save(update_fields=['legacy_unit_id', 'legacy_unit_name', 'legacy_sensor_type_id', 'legacy_sensor_type_name'])

    # Copy Device FK values and names to legacy fields
    for device in Device.objects.all():
        device.legacy_device_type_id = device.device_type_id
        device.legacy_device_type_name = device_type_names.get(device.device_type_id, '') if device.device_type_id else ''
        device.save(update_fields=['legacy_device_type_id', 'legacy_device_type_name'])

    # Copy SensorType.unit_id and name to legacy field
    for st in SensorType.objects.all():
        st.legacy_unit_id = st.unit_id
        st.legacy_unit_name = unit_names.get(st.unit_id, '') if st.unit_id else ''
        st.save(update_fields=['legacy_unit_id', 'legacy_unit_name'])

    print(f"  Preserved legacy data: {Sensor.objects.count()} sensors, {Device.objects.count()} devices, {SensorType.objects.count()} sensor types")


def clear_fks_and_delete_old_data(apps, schema_editor):
    """Clear FK fields and delete old Unit/DeviceType/SensorType records."""
    Sensor = apps.get_model('sensors', 'Sensor')
    Device = apps.get_model('sensors', 'Device')
    Unit = apps.get_model('sensors', 'Unit')
    DeviceType = apps.get_model('sensors', 'DeviceType')
    SensorType = apps.get_model('sensors', 'SensorType')

    # Clear FK fields on Sensor
    Sensor.objects.all().update(unit_id=None, sensor_type_id=None)

    # Clear FK fields on Device
    Device.objects.all().update(device_type_id=None)

    # Clear FK field on SensorType (unit_id)
    SensorType.objects.all().update(unit_id=None)

    # Count before delete for reporting
    unit_count = Unit.objects.count()
    dt_count = DeviceType.objects.count()
    st_count = SensorType.objects.count()

    # Now safe to delete all records from the type tables
    SensorType.objects.all().delete()
    DeviceType.objects.all().delete()
    Unit.objects.all().delete()

    print(f"  Deleted old data: {unit_count} units, {dt_count} device types, {st_count} sensor types")


def seed_from_yaml(apps, schema_editor):
    """Seed Unit, DeviceType, SensorType from YAML files (source of truth)."""
    Unit = apps.get_model('sensors', 'Unit')
    DeviceType = apps.get_model('sensors', 'DeviceType')
    SensorType = apps.get_model('sensors', 'SensorType')

    # --- Seed Units ---
    # Note: Units don't need aliases - they're associated via SensorType, not matched from device data
    units_data = load_yaml_file('units.yaml')
    for unit in units_data.get('units', []):
        Unit.objects.create(
            id=unit['id'],
            name=unit['name'],
            symbol=unit.get('symbol', ''),
            is_system=True,  # All seeded data is system/immutable
        )
    print(f"  Seeded {Unit.objects.count()} Units from units.yaml")

    # --- Seed DeviceTypes ---
    dt_data = load_yaml_file('device_types.yaml')
    for dt in dt_data.get('device_types', []):
        DeviceType.objects.create(
            id=dt['id'],
            name=dt['name'],
            icon=dt.get('icon', 'bi-device-hdd'),
            description=dt.get('description', ''),
            aliases=dt.get('aliases', []),
            is_system=True,  # All seeded data is system/immutable
            is_active=True,
        )
    print(f"  Seeded {DeviceType.objects.count()} DeviceTypes from device_types.yaml")

    # --- Seed SensorTypes ---
    st_data = load_yaml_file('sensor_types.yaml')
    for st in st_data.get('sensor_types', []):
        SensorType.objects.create(
            id=st['id'],
            name=st['name'],
            description=st.get('description', ''),
            graph_type=st.get('graph_type', 'LINE'),
            decimal_places=st.get('decimal_places', 2),
            min_value=st.get('min_value'),
            max_value=st.get('max_value'),
            allow_override=st.get('allow_override', False),
            unit_id=st.get('unit_id'),
            aliases=st.get('aliases', []),
            is_system=True,  # All seeded data is system/immutable
        )
    print(f"  Seeded {SensorType.objects.count()} SensorTypes from sensor_types.yaml")


def set_sequence_start(apps, schema_editor):
    """Set auto-increment to start at 100 for user-created data."""
    db_vendor = connection.vendor

    if db_vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("SELECT setval(pg_get_serial_sequence('sensors_unit', 'id'), 100, false);")
            cursor.execute("SELECT setval(pg_get_serial_sequence('sensors_devicetype', 'id'), 100, false);")
            cursor.execute("SELECT setval(pg_get_serial_sequence('sensors_sensortype', 'id'), 100, false);")
    elif db_vendor == 'sqlite':
        with connection.cursor() as cursor:
            cursor.execute("INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES ('sensors_unit', 99);")
            cursor.execute("INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES ('sensors_devicetype', 99);")
            cursor.execute("INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES ('sensors_sensortype', 99);")
    elif db_vendor == 'mysql':
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE sensors_unit AUTO_INCREMENT = 100;")
            cursor.execute("ALTER TABLE sensors_devicetype AUTO_INCREMENT = 100;")
            cursor.execute("ALTER TABLE sensors_sensortype AUTO_INCREMENT = 100;")


def reverse_migration(apps, schema_editor):
    """Reverse: delete seeded data (legacy data is lost)."""
    Unit = apps.get_model('sensors', 'Unit')
    DeviceType = apps.get_model('sensors', 'DeviceType')
    SensorType = apps.get_model('sensors', 'SensorType')

    SensorType.objects.all().delete()
    DeviceType.objects.all().delete()
    Unit.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0001_initial'),
    ]

    operations = [
        # Step 0a: Add is_system field to Unit (no aliases - units come from SensorType)
        migrations.AddField(
            model_name='unit',
            name='is_system',
            field=models.BooleanField(default=False, help_text='System records are immutable'),
        ),

        # Step 0b: Add aliases and is_system fields to DeviceType
        migrations.AddField(
            model_name='devicetype',
            name='aliases',
            field=models.JSONField(default=list, blank=True, help_text='List of alternative names that map to this device type'),
        ),
        migrations.AddField(
            model_name='devicetype',
            name='is_system',
            field=models.BooleanField(default=False, help_text='System records are immutable'),
        ),

        # Step 0c: Add aliases and is_system fields to SensorType
        migrations.AddField(
            model_name='sensortype',
            name='aliases',
            field=models.JSONField(default=list, blank=True, help_text='List of alternative names that map to this sensor type'),
        ),
        migrations.AddField(
            model_name='sensortype',
            name='is_system',
            field=models.BooleanField(default=False, help_text='System records are immutable'),
        ),

        # Step 1: Add legacy fields to Sensor (ID and NAME)
        migrations.AddField(
            model_name='sensor',
            name='legacy_unit_id',
            field=models.IntegerField(null=True, blank=True, help_text='Legacy unit_id before migration'),
        ),
        migrations.AddField(
            model_name='sensor',
            name='legacy_unit_name',
            field=models.CharField(max_length=100, null=True, blank=True, help_text='Legacy unit name before migration'),
        ),
        migrations.AddField(
            model_name='sensor',
            name='legacy_sensor_type_id',
            field=models.IntegerField(null=True, blank=True, help_text='Legacy sensor_type_id before migration'),
        ),
        migrations.AddField(
            model_name='sensor',
            name='legacy_sensor_type_name',
            field=models.CharField(max_length=100, null=True, blank=True, help_text='Legacy sensor type name before migration'),
        ),

        # Step 2: Add legacy fields to Device (ID and NAME)
        migrations.AddField(
            model_name='device',
            name='legacy_device_type_id',
            field=models.IntegerField(null=True, blank=True, help_text='Legacy device_type_id before migration'),
        ),
        migrations.AddField(
            model_name='device',
            name='legacy_device_type_name',
            field=models.CharField(max_length=100, null=True, blank=True, help_text='Legacy device type name before migration'),
        ),

        # Step 3: Add legacy fields to SensorType (for unit_id)
        migrations.AddField(
            model_name='sensortype',
            name='legacy_unit_id',
            field=models.IntegerField(null=True, blank=True, help_text='Legacy unit_id before migration'),
        ),
        migrations.AddField(
            model_name='sensortype',
            name='legacy_unit_name',
            field=models.CharField(max_length=100, null=True, blank=True, help_text='Legacy unit name before migration'),
        ),

        # Step 4: Copy FK values AND names to legacy fields
        migrations.RunPython(copy_fks_to_legacy, reverse_code=migrations.RunPython.noop),

        # Step 5: Clear FKs and delete old data
        migrations.RunPython(clear_fks_and_delete_old_data, reverse_code=migrations.RunPython.noop),

        # Step 6: Seed new standardized data from YAML files
        migrations.RunPython(seed_from_yaml, reverse_code=reverse_migration),

        # Step 7: Set auto-increment sequences to start at 100
        migrations.RunPython(set_sequence_start, reverse_code=migrations.RunPython.noop),
    ]
