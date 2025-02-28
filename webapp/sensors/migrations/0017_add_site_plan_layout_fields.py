from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('sensors', '0016_alter_device_serial_number'),  # Replace with your last migration
    ]

    operations = [
        migrations.AddField(
            model_name='place',
            name='site_plan_scale',
            field=models.FloatField(default=1.0),
        ),
        migrations.AddField(
            model_name='place',
            name='site_plan_x',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='place',
            name='site_plan_y',
            field=models.FloatField(default=0),
        ),
    ] 