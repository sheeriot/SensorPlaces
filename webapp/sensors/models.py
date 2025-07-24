from django.db import models
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.db.models.functions import Lower
from django.db.models import CharField, TextField, DecimalField, BooleanField, DateTimeField, ImageField, FloatField, ForeignKey

from django.conf import settings
from typing import Any, Optional
from datetime import datetime
from decimal import Decimal

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
    siteplan_image: ImageField = models.ImageField(
        upload_to='siteplan_images/',
        null=True,
        blank=True,
        validators=[validate_image_size]
    )
    created_at: DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: DateTimeField = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """Return the name of the place."""
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        """Return a formatted display name for the place."""
        return self.name

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

    def get_siteplan_url(self) -> Optional[str]:
        """Safely get the siteplan image URL or return None."""
        if self.siteplan_image and hasattr(self.siteplan_image, 'url'):
            return self.siteplan_image.url
        return None

    class Meta:
        verbose_name_plural = '1. Places'
        ordering = ['-is_active', Lower('name')]

class Location(models.Model):
    name: CharField = models.CharField(max_length=100)
    slug: CharField = models.SlugField(max_length=100, blank=True)
    place: ForeignKey = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='locations')
    x_pos: DecimalField = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('50.00'),  # Center horizontally
        null=True,
        blank=True
    )
    y_pos: DecimalField = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('50.00'),  # Center vertically
        null=True,
        blank=True
    )
    is_active: BooleanField = models.BooleanField(
        default=True,
        # help_text="inactive locations will be hidden by default"
    )
    created_at: DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: DateTimeField = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        # Ensure location can't be active if place is inactive
        if self.is_active and not self.place.is_active:
            raise ValidationError({
                'is_active': 'Location cannot be active when its place is inactive.'
            })

    def save(self, *args, **kwargs):
        # Run full validation first
        self.full_clean()
        
        # If parent place is inactive, location must be inactive
        if hasattr(self, 'place') and self.place and not self.place.is_active:
            self.is_active = False
        
        # Auto-generate slug if it's not set
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure slug is unique for the place
            original_slug = self.slug
            queryset = Location.objects.filter(place=self.place, slug=self.slug).exclude(pk=self.pk)
            counter = 1
            while queryset.exists():
                self.slug = f'{original_slug}-{counter}'
                counter += 1
                queryset = Location.objects.filter(place=self.place, slug=self.slug).exclude(pk=self.pk)

        # If location is being deactivated, deactivate all its devices
        if not self.is_active and self.pk:  # Only for existing locations
            Device.objects.filter(location=self).update(is_active=False)
            
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.place.name})"

    @property
    def x_coord_value(self) -> Optional[float]:
        return float(self.x_pos) if self.x_pos is not None else None

    @property
    def y_coord_value(self) -> Optional[float]:
        return float(self.y_pos) if self.y_pos is not None else None

    class Meta:
        verbose_name_plural = '2. Locations'
        ordering = ['-is_active', 'name']
        unique_together = ('place', 'slug')

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
    device_id: CharField = models.CharField(max_length=100, unique=True, null=True, blank=True)
    place: ForeignKey = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='devices', null=True, blank=True)
    location: ForeignKey = models.ForeignKey(
        Location, 
        on_delete=models.SET_NULL, 
        related_name='devices',
        null=True,
        blank=True
    )
    device_type = models.ForeignKey(
        DeviceType,
        on_delete=models.SET_NULL,
        related_name='devices',
        null=True
    )
    is_lorawan: BooleanField = models.BooleanField(default=False, verbose_name="LoRaWAN Device")
    is_active: BooleanField = models.BooleanField(
        default=True,
        help_text="inactive devices will be hidden by default"
    )
    created_at: DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: DateTimeField = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        # Ensure device can't be active if location is inactive
        if self.is_active and self.location and not self.location.is_active:
            raise ValidationError({
                'is_active': 'Device cannot be active when its location is inactive.'
            })

    def save(self, *args, **kwargs):
        # If location is set, ensure place is consistent
        if self.location:
            self.place = self.location.place

        if self.device_id:
            self.device_id = self.device_id.lower()

        # Run full validation first
        self.full_clean()
        
        # If location is inactive, device must be inactive
        if self.location and not self.location.is_active:
            self.is_active = False
        
        # Check if this is an existing device being deactivated
        if self.pk and not self.is_active:
            # Deactivate all associated sensors
            Sensor.objects.filter(device=self).update(is_active=False)
            
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.model})"

    class Meta:
        verbose_name_plural = '4. Devices'
        ordering = ['place', 'location', '-is_active', Lower('name')]

class InfluxSource(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='influx_sources')
    name = models.CharField(max_length=100)
    url = models.CharField(max_length=255)
    org = models.CharField(max_length=100)
    bucket_name = models.CharField(max_length=100)
    token = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.url})"

    class Meta:
        verbose_name_plural = 'InfluxDB Sources'

class Sensor(models.Model):
    """A sensor that can be attached to a device."""
    SENSOR_TYPES = [
        ('TEMPERATURE', 'Temperature'),
        ('HUMIDITY', 'Humidity'),
        ('PRESSURE', 'Pressure'),
        ('LIGHT', 'Light'),
        ('SOUND', 'Sound'),
        ('MOTION', 'Motion'),
        ('CO2', 'Carbon Dioxide'),
        ('VOC', 'Volatile Organic Compounds'),
        ('PM25', 'Particulate Matter 2.5'),
        ('PM10', 'Particulate Matter 10'),
        ('OTHER', 'Other'),
    ]
    DATA_TYPES = [
        ('DIRECT', 'Direct'),
        ('INFLUX', 'InfluxDB'),
    ]
    UNITS = [
        ('C', '°C'),
        ('F', '°F'),
        ('K', 'K'),
        ('RH', '%RH'),
        ('PA', 'Pa'),
        ('HPA', 'hPa'),
        ('LUX', 'lux'),
        ('DB', 'dB'),
        ('PPM', 'ppm'),
        ('PPB', 'ppb'),
        ('UGM3', 'μg/m³'),
        ('NONE', '(None)'),
    ]

    name: CharField = models.CharField(max_length=100)
    device: ForeignKey = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='sensors')
    is_active: BooleanField = models.BooleanField(default=True, verbose_name='Active Status')
    sensor_type: CharField = models.CharField(max_length=20, choices=SENSOR_TYPES)
    unit: CharField = models.CharField(max_length=10, choices=UNITS)
    
    # For data source
    data_type: CharField = models.CharField(max_length=10, choices=DATA_TYPES, default='DIRECT')
    influx_source: ForeignKey = models.ForeignKey(InfluxSource, on_delete=models.SET_NULL, null=True, blank=True, related_name='sensors')
    influx_measurement: CharField = models.CharField(max_length=100, null=True, blank=True)
    created_at: DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: DateTimeField = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        # Ensure sensor can't be active if device is inactive
        if self.is_active and not self.device.is_active:
            raise ValidationError({
                'is_active': 'Sensor cannot be active when its device is inactive.'
            })
            
        # Also check if the device's location is inactive
        if self.is_active and self.device.location and not self.device.location.is_active:
            raise ValidationError({
                'is_active': 'Sensor cannot be active when its device\'s location is inactive.'
            })

    def save(self, *args, **kwargs):
        # Run validation
        self.full_clean()
        
        # If device is inactive, sensor must be inactive
        if not self.device.is_active:
            self.is_active = False
        
        # Also check if the device's location is inactive
        if self.device.location and not self.device.location.is_active:
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

class ToastNotification(models.Model):
    """Persistent storage for toast notifications"""
    TOAST_TYPES = [
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('info', 'Info'),
        ('danger', 'Danger')
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='toast_notifications'
    )
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TOAST_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    place = models.ForeignKey(
        'Place',
        on_delete=models.CASCADE,
        null=True,
        related_name='toast_notifications'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['place', '-created_at']),
            models.Index(fields=['user', 'place', '-created_at']),
        ]

    @classmethod
    def get_unread_count(cls, user, place):
        """
        Get count of unread notifications for a user in a specific place.
        Uses a single efficient database query.
        """
        return cls.objects.filter(
            user=user,
            place=place
        ).exclude(
            toastreadstatus__user=user
        ).count()

    @classmethod
    def get_unread_for_place(cls, user, place):
        """
        Get all unread notifications for a user in a specific place.
        Uses a single efficient database query with annotations.
        """
        return cls.objects.filter(
            user=user,
            place=place
        ).exclude(
            toastreadstatus__user=user
        ).select_related('place').order_by('-created_at')

class ToastReadStatus(models.Model):
    """Tracks which toasts have been read by which users"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    toast = models.ForeignKey(ToastNotification, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'toast']
        indexes = [
            models.Index(fields=['user', 'toast']),
        ]
