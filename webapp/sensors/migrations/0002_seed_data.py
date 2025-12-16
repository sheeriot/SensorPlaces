# Migration 002: Add system fields and seed from YAML
#
# This migration:
# 1. Adds aliases (JSONField) and is_system (BooleanField) fields
# 2. Seeds standardized data from YAML files (source of truth)
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


def seed_from_yaml(apps, schema_editor):
    """Seed Unit, DeviceType, SensorType from YAML files (source of truth)."""
    Unit = apps.get_model('sensors', 'Unit')
    DeviceType = apps.get_model('sensors', 'DeviceType')
    SensorType = apps.get_model('sensors', 'SensorType')

    # --- Seed Units ---
    units_data = load_yaml_file('units.yaml')
    for unit in units_data.get('units', []):
        Unit.objects.create(
            id=unit['id'],
            name=unit['name'],
            symbol=unit.get('symbol', ''),
            is_system=True,
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
            is_system=True,
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
            is_system=True,
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
    """Reverse: delete seeded data."""
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
        # Add is_system field to Unit
        migrations.AddField(
            model_name='unit',
            name='is_system',
            field=models.BooleanField(default=False, help_text='System records are immutable'),
        ),

        # Add aliases and is_system fields to DeviceType
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

        # Add aliases and is_system fields to SensorType
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

        # Seed data from YAML files
        migrations.RunPython(seed_from_yaml, reverse_code=reverse_migration),

        # Set auto-increment sequences to start at 100
        migrations.RunPython(set_sequence_start, reverse_code=migrations.RunPython.noop),
    ]
