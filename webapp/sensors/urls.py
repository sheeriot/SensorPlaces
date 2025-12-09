from django.conf import settings
from django.urls import path, include
from .views import (
    place_views,
    location_views,
    device_views,
    sensor_views,
    influx_views,
    webhook_views,
    toggle_active,
    sensor_type_views,
    device_type_views,
    timezone_views,
    toast_views,
    switchbot_views,
)
from .views.sensor_views import (
    SensorCreateView,
    LoRaWANSensorCreateView,
    SensorListView,
    SensorDetailView,
    SensorUpdateView,
    SensorDeleteView,
    SensorGraphCardView,
    SensorDetailCardView,
    SensorLiveDetailsView,
    SensorInfluxUpdateView,
)

app_name = 'sensors'

urlpatterns = [
    # Place URLs (now at root)
    path('', place_views.PlaceListView.as_view(), name='place_list'),
    # Legacy URL for /places/
    path('places/', place_views.PlaceListView.as_view(), name='place_list_legacy'),
    path('new/', place_views.PlaceCreateView.as_view(), name='place_create'),

    # API, sensortype, and other specific patterns before the generic <place_slug>
    path('api/set-timezone/', timezone_views.set_user_timezone, name='set_user_timezone'),
    path('sensortypes/', sensor_type_views.SensorTypeListView.as_view(), name='sensortype_list'),
    path('sensortype/create/', sensor_type_views.SensorTypeCreateView.as_view(), name='sensortype_create'),
    path('sensortype/<int:pk>/', sensor_type_views.SensorTypeDetailView.as_view(), name='sensortype_detail'),
    path('sensortype/<int:pk>/update/', sensor_type_views.SensorTypeUpdateView.as_view(), name='sensortype_update'),

    # DeviceType URLs
    path('devicetypes/', device_type_views.DeviceTypeListView.as_view(), name='devicetype_list'),
    path('devicetype/create/', device_type_views.DeviceTypeCreateView.as_view(), name='devicetype_create'),
    path('devicetype/<int:pk>/', device_type_views.DeviceTypeDetailView.as_view(), name='devicetype_detail'),
    path('devicetype/<int:pk>/update/', device_type_views.DeviceTypeUpdateView.as_view(), name='devicetype_update'),

    # Webhook URLs
    path('webhook/switchbot/<slug:place_slug>/', webhook_views.SwitchBotWebhookReceiverView.as_view(), name='switchbot_webhook_receiver'),
    path('webhook/shelly/<slug:place_slug>/', webhook_views.ShellyWebhookReceiverView.as_view(), name='shelly_webhook_receiver_gen1'),
    path('webhook/shelly/<slug:place_slug>/<str:device_id>/', webhook_views.ShellyWebhookReceiverView.as_view(), name='shelly_webhook_receiver'),
    path('webhook/<slug:place_slug>/<uuid:uuid>/', webhook_views.WebhookReceiverView.as_view(), name='webhook_receiver'),

    # Place-specific URLs
    path('<slug:place_slug>/', place_views.PlaceDetailView.as_view(), name='place_detail'),
    path('<slug:place_slug>/update/', place_views.PlaceUpdateView.as_view(), name='place_update'),
    path('<slug:place_slug>/delete/', place_views.PlaceDeleteView.as_view(), name='place_delete'),
    path('<slug:place_slug>/map/', place_views.place_map_modal_view, name='place_map_modal'),
    path('<slug:place_slug>/siteplan/', place_views.siteplan_view, name='siteplan'),
    path('<slug:place_slug>/siteplan/view-modal/', place_views.siteplan_view_modal, name='siteplan_view_modal'),
    path('<slug:place_slug>/siteplan/edit-modal/', place_views.siteplan_editor_modal, name='siteplan_editor_modal'),
    path('<slug:place_slug>/siteplan/update/', place_views.siteplan_update, name='siteplan_update'),

    # SwitchBot Integration
    path('<slug:place_slug>/switchbot/', switchbot_views.switchbot_management_view, name='switchbot_management'),
    # path('<slug:place_slug>/switchbot/existing-devices/', switchbot_views.switchbot_existing_devices_view, name='switchbot_existing_devices'),
    # path('<slug:place_slug>/switchbot/api-sync/', switchbot_views.switchbot_api_sync_view, name='switchbot_api_sync'),
    # path('<slug:place_slug>/switchbot/config/', switchbot_views.switchbot_config_update_view, name='switchbot_config_update'),
    # path('<slug:place_slug>/switchbot/edit-influx-store/', switchbot_views.switchbot_influx_store_edit_view, name='switchbot_influx_store_edit'),
    # path('<slug:place_slug>/switchbot/update-influx-store/', switchbot_views.update_switchbot_influx_store, name='switchbot_influx_store_update'),
    # path('<slug:place_slug>/switchbot/import-device/', switchbot_views.import_switchbot_device_view, name='import_switchbot_device'),
    # path('<slug:place_slug>/switchbot/inspect-api-device/<str:device_id>/', switchbot_views.switchbot_inspect_api_device_view, name='switchbot_inspect_api_device'),

    # API URLs that are place-specific
    path('api/<slug:place_slug>/stats/', place_views.place_stats, name='place_stats_api'),
    path('api/<slug:place_slug>/toggle-active/', toggle_active.ToggleActiveView.as_view(), name='toggle_active'),
    path('api/<slug:place_slug>/toasts/', toast_views.ToastAPIView.as_view(), name='toast_api'),

    # Location URLs
    path('<slug:place_slug>/location/', location_views.LocationListView.as_view(), name='location_list'),
    path('<slug:place_slug>/location/new/', location_views.LocationCreateView.as_view(), name='location_create'),
    path('<slug:place_slug>/location/create-modal/', location_views.LocationCreateModalView.as_view(), name='location_create_modal'),
    path('<slug:place_slug>/location/<slug:slug>/', location_views.LocationDetailView.as_view(), name='location_detail'),
    path('<slug:place_slug>/location/<slug:slug>/update/', location_views.LocationUpdateView.as_view(), name='location_update'),
    path('<slug:place_slug>/location/<slug:slug>/delete/', location_views.LocationDeleteView.as_view(), name='location_delete'),

    # Device URLs
    path('<slug:place_slug>/devices/', device_views.DeviceListView.as_view(), name='device_list'),
    path('<slug:place_slug>/unassigned-devices/', device_views.UnassignedDeviceListView.as_view(), name='unassigned_device_list'),
    path('<slug:place_slug>/device/create/', device_views.DeviceCreateView.as_view(), name='device_create'),
    path('<slug:place_slug>/location/<slug:location_slug>/device/create/', device_views.DeviceCreateView.as_view(), name='device_create_in_location'),
    path('<slug:place_slug>/device/<int:pk>/', device_views.DeviceDetailView.as_view(), name='device_detail'),
    path('<slug:place_slug>/device/<int:pk>/update/', device_views.DeviceUpdateView.as_view(), name='device_update'),
    path('<slug:place_slug>/device/<int:pk>/delete/', device_views.DeviceDeleteView.as_view(), name='device_delete'),
    path('<slug:place_slug>/device/<int:pk>/fetch-reading/', switchbot_views.fetch_switchbot_reading, name='fetch_switchbot_reading'),
    path('<slug:place_slug>/device/<int:pk>/inspect/', switchbot_views.SwitchbotInspectView.as_view(), name='inspect_switchbot_device'),

    # API endpoints for devices
    path('api/<slug:place_slug>/device/<int:pk>/move/', device_views.DeviceMoveLocationView.as_view(), name='device_move_location'),
    # path('api/<slug:place_slug>/device/<int:device_pk>/switchbot_missing_sensors/', device_views.get_missing_switchbot_sensors, name='get_missing_switchbot_sensors'),
    # path('api/<slug:place_slug>/device/<int:device_pk>/switchbot_get_devices/', device_views.get_switchbot_devices, name='get_switchbot_devices'),
    # path('api/<slug:place_slug>/device/<int:device_pk>/switchbot_add_sensor/', device_views.add_switchbot_sensor, name='add_switchbot_sensor'),

    # Toast URLs
    path('<slug:place_slug>/toasts/', toast_views.ToastListView.as_view(), name='toast_list'),

    # Sensor URLs
    path('<slug:place_slug>/device/<int:device_pk>/sensor/create/', SensorCreateView.as_view(), name='sensor_create'),
    path('<slug:place_slug>/device/<int:device_pk>/lorawan-sensor/create/', LoRaWANSensorCreateView.as_view(), name='lorawan_sensor_create'),
    path('<slug:place_slug>/device/<int:device_pk>/add-switchbot-sensor/', switchbot_views.add_switchbot_sensor, name='add_switchbot_sensor'),
    path('<slug:place_slug>/sensors/', SensorListView.as_view(), name='sensor_list'),
    path('<slug:place_slug>/location/<int:location_pk>/sensors/', SensorListView.as_view(), name='location_sensors'),
    path('<slug:place_slug>/device/<int:device_pk>/sensors/', SensorListView.as_view(), name='device_sensors'),
    path('<slug:place_slug>/sensor/<int:pk>/', SensorDetailView.as_view(), name='sensor_detail'),
    path('<slug:place_slug>/sensor/<int:pk>/card/', SensorDetailCardView.as_view(), name='sensor_detail_card'),
    path('<slug:place_slug>/sensor/<int:pk>/live-details/', SensorLiveDetailsView.as_view(), name='sensor_live_details'),
    path('<slug:place_slug>/sensor/<int:pk>/delta/<str:delta>/', SensorDetailView.as_view(), name='sensor_detail_delta'),
    path('<slug:place_slug>/sensor/<int:pk>/<str:start_date>/<str:end_date>/', SensorDetailView.as_view(), name='sensor_detail_daterange'),
    path('<slug:place_slug>/sensor/<int:pk>/graph-card/', SensorGraphCardView.as_view(), name='sensor_graph_card'),
    path('<slug:place_slug>/sensor/<int:pk>/live-value/', sensor_views.sensor_live_value_view, name='sensor_live_value'),
    path('<slug:place_slug>/sensor/<int:pk>/live-row/', sensor_views.sensor_live_row_view, name='sensor_live_row'),
    path('<slug:place_slug>/sensor/<int:pk>/update/', SensorUpdateView.as_view(), name='sensor_update'),
    path('<slug:place_slug>/sensor/<int:pk>/update-influx/', SensorInfluxUpdateView.as_view(), name='sensor_influx_update'),
    path('<slug:place_slug>/sensor/<int:pk>/delete/', SensorDeleteView.as_view(), name='sensor_delete'),
    path('<slug:place_slug>/sensor/<int:sensor_pk>/readings/', sensor_views.SensorReadingListView.as_view(), name='sensor_reading_list'),

    # API endpoints for sensor readings
    path('api/<slug:place_slug>/sensor/<int:pk>/test-influx-bucket/', sensor_views.test_influx_bucket_for_sensor, name='test_influx_bucket_for_sensor'),
    path('api/<slug:place_slug>/sensor/<int:pk>/update-graph-type/', sensor_views.update_graph_type, name='update_graph_type'),
    path('api/<slug:place_slug>/sensor/<int:pk>/readings/', sensor_views.sensor_readings_api, name='sensor_readings_api'),
    path('api/<slug:place_slug>/sensor/<int:sensor_pk>/readings_table/', sensor_views.sensor_readings_table_api, name='sensor_readings_table_api'),
    path('api/<slug:place_slug>/sensor/<int:pk>/lorawan_data/', sensor_views.lorawan_sensor_data_api, name='lorawan_sensor_data_api'),

    # InfluxStore URLs
    path('<slug:place_slug>/influxstores/create/', influx_views.InfluxStoreCreateView.as_view(), name='influxstore_create'),
    path('<slug:place_slug>/influxstores/<int:pk>/', influx_views.InfluxStoreDetailView.as_view(), name='influxstore_detail'),
    path('<slug:place_slug>/influxstores/<int:pk>/update/', influx_views.InfluxStoreUpdateView.as_view(), name='influxstore_update'),
    path('<slug:place_slug>/influxstores/<int:pk>/delete/', influx_views.InfluxStoreDeleteView.as_view(), name='influxstore_delete'),
    path('<slug:place_slug>/influxstores/<int:pk>/test/', influx_views.influxstore_test, name='influxstore_test'),
    path('api/<slug:place_slug>/influx-stores/<int:pk>/test-bucket/', influx_views.test_influx_store_bucket, name='test_influx_store_bucket'),
    path('api/<slug:place_slug>/influx-stores/<int:pk>/test-write/', influx_views.test_influx_store_write_read_view, name='test_influx_store_write'),
    path('<slug:place_slug>/sensor/<int:pk>/test-influx-write/', sensor_views.test_influx_write, name='test_influx_write'),
]

if settings.DEBUG:
    urlpatterns += [
        path('dev/', include('sensors.dev_urls', namespace='sensors_dev')),
    ]
