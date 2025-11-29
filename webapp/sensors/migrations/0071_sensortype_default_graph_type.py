from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0070_remove_sensor_data_type_override'),
    ]

    operations = [
        migrations.AddField(
            model_name='sensortype',
            name='default_graph_type',
            field=models.CharField(choices=[('LINE', 'Line Graph'), ('SCATTER', 'Scatter Plot'), ('BAR', 'Bar Graph')], default='SCATTER', max_length=20),
        ),
    ]
