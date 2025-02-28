from django.db import migrations

def create_device_types(apps, schema_editor):
    DeviceType = apps.get_model('sensors', 'DeviceType')
    
    # Define the device types with their icons and descriptions
    device_types = [
        {
            'name': 'Server',
            'icon': 'bi-server',
            'description': 'Server hardware for data processing and storage'
        },
        {
            'name': 'Gateway',
            'icon': 'bi-router',
            'description': 'Network gateway device for data transmission'
        },
        {
            'name': 'Controller',
            'icon': 'bi-cpu',
            'description': 'Control system for managing sensors and devices'
        },
        {
            'name': 'Data Logger',
            'icon': 'bi-journal-text',
            'description': 'Device for recording and storing sensor data'
        },
        {
            'name': 'Router',
            'icon': 'bi-router',
            'description': 'Network routing device'
        },
        {
            'name': 'Network Switch',
            'icon': 'bi-hdd-network',
            'description': 'Network switching device'
        },
        {
            'name': 'UPS',
            'icon': 'bi-battery',
            'description': 'Uninterruptible Power Supply'
        },
        {
            'name': 'Sensor Hub',
            'icon': 'bi-diagram-3',
            'description': 'Central hub for connecting multiple sensors'
        }
        # Note: 'Other' type was already created in the previous migration
    ]
    
    # Create each device type
    for device_type in device_types:
        DeviceType.objects.get_or_create(
            name=device_type['name'],
            defaults={
                'icon': device_type['icon'],
                'description': device_type['description'],
                'is_active': True
            }
        )

def remove_device_types(apps, schema_editor):
    DeviceType = apps.get_model('sensors', 'DeviceType')
    # Don't delete the 'Other' type as it might be in use
    DeviceType.objects.exclude(name='Other').delete()

class Migration(migrations.Migration):
    dependencies = [
        ('sensors', '0013_devicetype_alter_device_options_and_more'),
    ]

    operations = [
        migrations.RunPython(
            create_device_types,
            reverse_code=remove_device_types
        ),
    ] 