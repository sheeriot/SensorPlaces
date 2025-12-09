from django.contrib import admin
from icecream import ic

from .models import (
    Place,
    Location,
    Device,
    DeviceType,
    Sensor,
    SensorType,
    Unit,
    SensorReading,
    InfluxStore,
    ToastNotification,
    ToastReadStatus,
)
from .utils import update_sensor_live_value


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
    list_display = ('name', 'place_name', 'location', 'device_type', 'is_active', 'model', 'manufacturer', 'device_id', 'is_switchbot')
    list_filter = ('is_active', 'is_switchbot', 'location__place', 'location', 'device_type', 'manufacturer')
    search_fields = ('name', 'device_id', 'location__place__name', 'location__name')
    readonly_fields = ('location',)
    list_editable = ('is_active', 'is_switchbot',)
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


@admin.register(SensorType)
class SensorTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'graph_type', 'allow_override', 'min_value', 'max_value', 'decimal_places')
    search_fields = ('name', 'description')
    list_filter = ('allow_override',)
    ordering = ('name',)
    fieldsets = (
        (None, {
            'fields': ('name', 'description')
        }),
        ('Defaults and Overrides', {
            'fields': ('unit', 'graph_type', 'allow_override')
        }),
        ('Value Configuration', {
            'fields': ('min_value', 'max_value', 'decimal_places')
        }),
    )

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol')
    search_fields = ('name', 'symbol')
    ordering = ('name',)

@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ('name', 'device', 'sensor_type', 'effective_unit_display', 'data_store_display', 'is_active')
    list_filter = ('sensor_type', 'is_active', 'device__location')
    search_fields = ('name', 'device__name')
    readonly_fields = ()
    autocomplete_fields = ['device', 'sensor_type', 'influx_store']

    fieldsets = (
        ('General', {
            'fields': ('name', 'device', 'sensor_type', 'is_active')
        }),
        ('Data Source', {
            'fields': ('data_store', 'influx_store', 'influx_measurement', 'influx_field_name', 'influx_tag_key')
        }),
        ('Overrides', {
            'fields': ('unit_override', 'unit', 'min_value_override', 'min_value', 'max_value_override', 'max_value', 'graph_type')
        }),
        ('Cached Value', {
            'fields': ('cached_reading_value', 'cached_reading_timestamp', 'last_cached_timestamp', 'stale_threshold_seconds')
        }),
    )

    def get_queryset(self, request):
        """
        Override to update live sensor values before displaying them.
        """
        queryset = super().get_queryset(request)
        for sensor in queryset:
            if sensor.data_store and sensor.data_store.startswith('INFLUX'):
                update_sensor_live_value(sensor)
        return queryset

    def get_object(self, request, object_id, from_field=None):
        """
        Override to update the live value for a single sensor when viewing its detail page.
        """
        obj = super().get_object(request, object_id, from_field)
        if obj and obj.data_store and obj.data_store.startswith('INFLUX'):
            update_sensor_live_value(obj)
        return obj

    def effective_unit_display(self, obj):
        if obj.effective_unit:
            return obj.effective_unit.symbol
        return "N/A"
    effective_unit_display.short_description = 'Unit'

    def data_store_display(self, obj):
        return obj.get_data_store_display()
    data_store_display.short_description = 'Data Store'

    class Meta:
        verbose_name_plural = '4. Sensors'


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'value', 'timestamp')
    list_filter = ('sensor', 'timestamp', 'sensor__device')
    search_fields = ('sensor__name', 'notes')

    class Meta:
        verbose_name_plural = '5. Sensor Readings'


@admin.register(InfluxStore)
class InfluxStoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'place', 'url', 'org', 'bucket_name')
    list_filter = ('place',)
    search_fields = ('name', 'url', 'org', 'bucket_name')

@admin.register(ToastNotification)
class ToastNotificationAdmin(admin.ModelAdmin):
    list_display = ('place','user', 'message', 'type', 'created_at')
    list_filter = ('place', 'user', 'type',)
    search_fields = ('place__name', 'user__username', 'message')
    readonly_fields = ('created_at','place','type','user', 'message')
