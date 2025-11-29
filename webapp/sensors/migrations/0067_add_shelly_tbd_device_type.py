from django.db import migrations

def create_shelly_tbd_device_type(apps, schema_editor):
    DeviceType = apps.get_model('sensors', 'DeviceType')
    DeviceType.objects.get_or_create(
        name='Shelly-TBD',
        defaults={
            'icon': 'bi-question-circle',
            'description': 'Generic Shelly device type for auto-created devices where the specific model is unknown.'
        }
    )

def remove_shelly_tbd_device_type(apps, schema_editor):
    DeviceType = apps.get_model('sensors', 'DeviceType')
    DeviceType.objects.filter(name='Shelly-TBD').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0066_alter_unit_symbol'),
    ]

    operations = [
        migrations.RunPython(create_shelly_tbd_device_type, remove_shelly_tbd_device_type),
    ]
