from django.db import migrations

def configure_sensor_type_defaults(apps, schema_editor):
    SensorType = apps.get_model('sensors', 'SensorType')

    # Temperature -> LINE
    try:
        st = SensorType.objects.get(name__iexact='Temperature')
        st.default_graph_type = 'LINE'
        st.save()
    except SensorType.DoesNotExist:
        pass

    # Battery Voltage -> LINE
    try:
        st = SensorType.objects.get(name__iexact='Battery Voltage')
        st.default_graph_type = 'LINE'
        st.save()
    except SensorType.DoesNotExist:
        pass

    # Water Detector -> BAR
    try:
        st = SensorType.objects.get(name__iexact='Water Detector')
        st.default_graph_type = 'BAR'
        st.save()
    except SensorType.DoesNotExist:
        pass

class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0071_sensortype_default_graph_type'),
    ]

    operations = [
        migrations.RunPython(configure_sensor_type_defaults),
    ]
