from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0067_add_shelly_tbd_device_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sensortype',
            name='default_data_type',
        ),
    ]
