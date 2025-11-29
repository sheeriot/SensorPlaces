from django.db import migrations

def enforce_allow_override_water_detector(apps, schema_editor):
    SensorType = apps.get_model('sensors', 'SensorType')
    try:
        water_detector = SensorType.objects.get(name__iexact='Water Detector')
        water_detector.allow_override = True
        water_detector.save()
    except SensorType.DoesNotExist:
        pass

class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0073_alter_sensor_graph_type_default'),
    ]

    operations = [
        migrations.RunPython(enforce_allow_override_water_detector),
    ]
