from django.db import migrations

def allow_override_for_water_detector(apps, schema_editor):
    SensorType = apps.get_model('sensors', 'SensorType')
    try:
        water_detector = SensorType.objects.get(name__iexact='Water Detector')
        water_detector.allow_override = True
        water_detector.save()
    except SensorType.DoesNotExist:
        pass

class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0068_remove_sensortype_default_data_type'),
    ]

    operations = [
        migrations.RunPython(allow_override_for_water_detector),
    ]
