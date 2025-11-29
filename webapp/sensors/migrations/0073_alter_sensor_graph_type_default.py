from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0072_configure_sensor_type_defaults'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sensor',
            name='graph_type',
            field=models.CharField(blank=True, choices=[('LINE', 'Line Graph'), ('SCATTER', 'Scatter Plot'), ('BAR', 'Bar Graph')], default=None, max_length=20, null=True),
        ),
    ]
