from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid

def validate_image_size(image):
    filesize = image.size
    megabyte_limit = 5.0
    if filesize > megabyte_limit * 1024 * 1024:
        raise ValidationError(f"Image size cannot exceed {megabyte_limit}MB")

class Place(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, null=True, blank=True)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_active = models.BooleanField(default=True)
    site_plan = models.ImageField(
        upload_to='site_plans/',
        null=True, 
        blank=True,
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png']),
            validate_image_size
        ],
        help_text="Upload a site plan image (JPG/PNG, minimum 1024x768, max 5MB)"
    )
    site_plan_scale = models.FloatField(default=1.0)
    site_plan_x = models.FloatField(default=0)
    site_plan_y = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = '1. Places'

class Location(models.Model):
    name = models.CharField(max_length=100)
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='locations')
    x_coord = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    y_coord = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive locations will be hidden by default"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # If location is being deactivated, deactivate all its devices
        if not self.is_active and self.pk:  # Only for existing locations
            Device.objects.filter(location=self).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} at {self.place.name}"

    class Meta:
        verbose_name_plural = '2. Locations'

class DeviceType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50,
        default='bi-hdd',
        help_text="Bootstrap icon class (e.g., bi-hdd, bi-router)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = '3. Device Types'
        ordering = ['name']

class Device(models.Model):
    name = models.CharField(max_length=100)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='devices')
    device_type = models.ForeignKey(
        DeviceType,
        on_delete=models.SET_NULL,
        related_name='devices',
        null=True
    )
    model = models.CharField(max_length=50, blank=True, help_text="Device model number or name")
    manufacturer = models.CharField(max_length=50, blank=True, help_text="Device manufacturer")
    serial_number = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive devices will be hidden by default"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.device_type.name})"

    def save(self, *args, **kwargs):
        # If location is inactive, device must be inactive
        if not self.location.is_active:
            self.is_active = False
        
        # Check if this is an existing device being deactivated
        if self.pk and not self.is_active:
            # Deactivate all associated sensors
            Sensor.objects.filter(device=self).update(is_active=False)
            
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = '4. Devices'

class InfluxSource(models.Model):
    name = models.CharField(max_length=100)
    server_dns = models.CharField(max_length=255)
    server_port = models.IntegerField(default=8086)
    bucket_name = models.CharField(max_length=100)
    org = models.CharField(max_length=100)
    read_token = models.CharField(max_length=255)
    write_token = models.CharField(max_length=255, blank=True, null=True)  # Optional
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.server_dns})"

    class Meta:
        verbose_name_plural = 'InfluxDB Sources'

class Sensor(models.Model):
    DATA_TYPES = [
        ('DB', 'Database'),
        ('INFLUX', 'InfluxDB'),
    ]
    
    SENSOR_TYPES = [
        ('TEMP', 'Temperature'),
        ('HUM', 'Humidity'),
        ('PRESS', 'Pressure'),
        ('CO2', 'Carbon Dioxide'),
        ('OTHER', 'Other'),
    ]

    UNITS = [
        ('°C', 'Celsius'),
        ('°F', 'Fahrenheit'),
        ('%', 'Percent'),
        ('hPa', 'Hectopascal'),
        ('ppm', 'Parts per Million'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='sensors')
    sensor_type = models.CharField(max_length=5, choices=SENSOR_TYPES)
    unit = models.CharField(max_length=10, choices=UNITS, default='other')
    data_type = models.CharField(max_length=10, choices=DATA_TYPES, default='DB')
    influx_source = models.ForeignKey(
        InfluxSource, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sensors'
    )
    influx_measurement = models.CharField(max_length=100, default='sensor_readings', blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive sensors will be hidden by default"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.is_active and not self.device.is_active:
            raise ValidationError({
                'is_active': 'Cannot activate a sensor that belongs to an inactive device.'
            })

    def save(self, *args, **kwargs):
        # Run validation
        self.full_clean()
        
        # If device is inactive, sensor must be inactive
        if not self.device.is_active:
            self.is_active = False
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_sensor_type_display()})"

    class Meta:
        verbose_name_plural = '5. Sensors'
        ordering = ['name']

class SensorReading(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='readings')
    value = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.sensor.name} - {self.value} at {self.timestamp}"

    class Meta:
        verbose_name_plural = '5. Sensor Readings'
