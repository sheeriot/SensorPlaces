# Migration 004: Remove legacy fields after transformation
#
# This migration removes the legacy_*_id and legacy_*_name fields that were
# used to preserve old FK values during the migration from legacy to
# standardized data.
#
# After this migration:
# - All FK relationships point to new standardized records
# - Legacy fields are removed (no longer needed)
# - Migrations 003 and 004 can be removed on next rebuild (fresh DBs have no legacy data)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0003_transform_legacy_data'),
    ]

    operations = [
        # Remove legacy fields from Sensor
        migrations.RemoveField(
            model_name='sensor',
            name='legacy_unit_id',
        ),
        migrations.RemoveField(
            model_name='sensor',
            name='legacy_unit_name',
        ),
        migrations.RemoveField(
            model_name='sensor',
            name='legacy_sensor_type_id',
        ),
        migrations.RemoveField(
            model_name='sensor',
            name='legacy_sensor_type_name',
        ),

        # Remove legacy fields from Device
        migrations.RemoveField(
            model_name='device',
            name='legacy_device_type_id',
        ),
        migrations.RemoveField(
            model_name='device',
            name='legacy_device_type_name',
        ),

        # Remove legacy fields from SensorType
        migrations.RemoveField(
            model_name='sensortype',
            name='legacy_unit_id',
        ),
        migrations.RemoveField(
            model_name='sensortype',
            name='legacy_unit_name',
        ),
    ]
