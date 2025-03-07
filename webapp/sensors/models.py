from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid
from django.db.models.functions import Lower
from typing import Any, Optional, Union, cast
from django.urls import reverse
from datetime import datetime
from decimal import Decimal
from django.db.models import CharField, TextField, DecimalField, BooleanField, DateTimeField, ImageField, FloatField, ForeignKey
from django.contrib.auth import get_user_model

def validate_image_size(image):
    filesize = image.size
    megabyte_limit = 5.0
    if filesize > megabyte_limit * 1024 * 1024:
        raise ValidationError(f"Image size cannot exceed {megabyte_limit}MB")

class Place(models.Model):
    name: CharField = models.CharField(max_length=100)
    slug: CharField = models.SlugField(unique=True, null=True, blank=True)
    address: TextField = models.TextField()
    latitude: DecimalField = models.DecimalField(max_digits=9, decimal_places=6)
    longitude: DecimalField = models.DecimalField(max_digits=9, decimal_places=6)
    is_active: BooleanField = models.BooleanField(default=True)
    site_plan: ImageField = models.ImageField(
        upload_to='site_plans/',
        null=True,
        blank=True,
        validators=[validate_image_size]
    )
    site_plan_scale = models.FloatField(default=1.0)
    site_plan_x: FloatField = models.FloatField(default=0)
    site_plan_y: FloatField = models.FloatField(default=0)
    created_at: DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: DateTimeField = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.name)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def name_str(self) -> str:
        return str(self.name)

    @property
    def slug_str(self) -> str:
        return str(self.slug)

    @property
    def address_str(self) -> str:
        return str(self.address)

    @property
    def latitude_value(self) -> float:
        return float(self.latitude)

    @property
    def longitude_value(self) -> float:
        return float(self.longitude)

    @property
    def is_active_bool(self) -> bool:
        return bool(self.is_active)

    @property
    def created_at_datetime(self) -> datetime:
        return self.created_at

    @property
    def updated_at_datetime(self) -> datetime:
        return self.updated_at

    class Meta:
        verbose_name_plural = '1. Places'
        ordering = ['-is_active', Lower('name')]

class Location(models.Model):
    name: CharField = models.CharField(max_length=100)
    place: ForeignKey = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='locations')
    x_coord: DecimalField = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    y_coord: DecimalField = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_active: BooleanField = models.BooleanField(
        default=True,
        help_text="Inactive locations will be hidden by default"
    )
    created_at: DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: DateTimeField = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # If location is being deactivated, deactivate all its devices
        if not self.is_active and self.pk:  # Only for existing locations
            Device.objects.filter(location=self).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.place.name})"

    @property
    def x_coord_value(self) -> Optional[float]:
        return float(self.x_coord) if self.x_coord is not None else None

    @property
    def y_coord_value(self) -> Optional[float]:
        return float(self.y_coord) if self.y_coord is not None else None

    class Meta:
        verbose_name_plural = '2. Locations'
        ordering = ['-is_active', 'name']

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
    name: CharField = models.CharField(max_length=100)
    model: CharField = models.CharField(max_length=100, null=True, blank=True)
    manufacturer: CharField = models.CharField(max_length=100, null=True, blank=True)
    serial_number: CharField = models.CharField(max_length=100, null=True, blank=True)
    location: ForeignKey = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='devices')
    device_type = models.ForeignKey(
        DeviceType,
        on_delete=models.SET_NULL,
        related_name='devices',
        null=True
    )
    is_active: BooleanField = models.BooleanField(
        default=True,
        help_text="Inactive devices will be hidden by default"
    )
    created_at: DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: DateTimeField = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.model})"

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
        ordering = ['location', '-is_active', Lower('name')]

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
        ('CO2', 'CO2'),
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

    name: CharField = models.CharField(max_length=100)
    sensor_type: CharField = models.CharField(max_length=50, choices=SENSOR_TYPES)
    device: ForeignKey = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='sensors')
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
    is_active: BooleanField = models.BooleanField(
        default=True,
        help_text="Inactive sensors will be hidden by default"
    )
    created_at: DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: DateTimeField = models.DateTimeField(auto_now=True)

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

    def __str__(self) -> str:
        return f"{self.name} ({self.get_sensor_type_display()})"

    def get_sensor_type_display(self) -> str:
        return dict(self.SENSOR_TYPES).get(self.sensor_type, 'Unknown')

    class Meta:
        verbose_name_plural = '5. Sensors'
        ordering = [
            Lower('device__location__name'),
            Lower('device__name'),
            '-is_active',
            Lower('name')
        ]

class SensorReading(models.Model):
    sensor: ForeignKey = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='readings')
    value: FloatField = models.FloatField()
    timestamp: DateTimeField = models.DateTimeField(auto_now_add=True)
    notes: TextField = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.sensor.name}: {self.value} at {self.timestamp}"

    @property
    def value_float(self) -> float:
        return float(self.value)

    class Meta:
        verbose_name_plural = '5. Sensor Readings'

class ToastMessage(models.Model):
    """Persistent storage for toast notifications"""
    TOAST_TYPES = [
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('info', 'Info'),
        ('danger', 'Danger')
    ]

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='toast_messages'
    )
    username = models.CharField(max_length=150)  # Match User model username max_length
    message = models.TextField()
    type = models.CharField(max_length=10, choices=TOAST_TYPES)
    tags = models.CharField(max_length=50)  # For additional styling/behavior flags
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['username', '-timestamp']),
        ]

    def save(self, *args, **kwargs):
        if not self.username and self.user:
            self.username = self.user.username
        super().save(*args, **kwargs)
