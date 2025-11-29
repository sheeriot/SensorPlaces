from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sensors', '0069_allow_override_water_detector'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sensor',
            name='data_type_override',
        ),
    ]
