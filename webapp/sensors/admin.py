from django.contrib import admin
from icecream import ic

from .models import (
    Place,
    Location,
    Device,
    DeviceType,
    Sensor,
    SensorReading,
    InfluxSource,
    ToastNotification,
)


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'latitude', 'longitude', 'is_active', 'created_at')
    search_fields = ('name', 'address')
    list_filter = ('is_active',)

    class Meta:
        ordering = ['name']
        verbose_name_plural = '1. Places'


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'place', 'created_at')
    search_fields = ('name', 'place__name')
    list_filter = ('place',)

    class Meta:
        verbose_name_plural = '2. Locations'


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'place_name', 'location', 'device_type', 'is_active', 'model', 'manufacturer', 'device_id')
    list_filter = ('is_active', 'location__place', 'location', 'device_type', 'manufacturer')
    search_fields = ('name', 'device_id', 'location__place__name', 'location__name')
    list_editable = ('is_active',)
    autocomplete_fields = ('location', 'device_type')
    ordering = ('name',)

    def place_name(self, obj):
        if obj.location:
            return obj.location.place.name
        return "N/A"
    place_name.short_description = 'Place'

    class Meta:
        verbose_name_plural = '3. Devices'


@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('name',)


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ('name', 'device', 'sensor_type', 'is_active')
    list_filter = ('sensor_type', 'is_active', 'device__location')
    search_fields = ('name', 'device__name')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'device', 'sensor_type', 'is_active', 'data_type')
        }),
        ('InfluxDB Settings', {
            'fields': ('influx_source', 'influx_measurement'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    class Meta:
        verbose_name_plural = '4. Sensors'


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'value', 'timestamp')
    list_filter = ('sensor', 'timestamp', 'sensor__device')
    search_fields = ('sensor__name', 'notes')

    class Meta:
        verbose_name_plural = '5. Sensor Readings'


@admin.register(InfluxSource)
class InfluxSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'place', 'url', 'bucket_name', 'org')
    search_fields = ('name', 'url', 'bucket_name', 'place__name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('place', 'name', 'url', 'bucket_name', 'org', 'token')
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return tuple(self.readonly_fields) + ('read_token',)
        return self.readonly_fields

@admin.register(ToastNotification)
class ToastNotificationAdmin(admin.ModelAdmin):
    list_display = ('place','user', 'message', 'type', 'created_at')
    list_filter = ('place', 'user', 'type',)
    search_fields = ('place__name', 'user__username', 'message')
    readonly_fields = ('created_at','place','type','user', 'message')
