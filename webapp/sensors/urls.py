from django.urls import path
from .views import (
    place_views,
    location_views,
    device_views,
    sensor_views,
    influx_views,
    webhook_views,
    toggle_active,
    sensor_type_views,
    timezone_views,
    toast_views,
)
from .views.sensor_views import (
    SensorCreateView,
    LoRaWANSensorCreateView,
    SensorListView,
    SensorDetailView,
    SensorUpdateView,
    SensorDeleteView,
)

app_name = 'sensors'

urlpatterns = [
    # Place URLs
    path('', place_views.PlaceListView.as_view(), name='place_list'),
    path('new/', place_views.PlaceCreateView.as_view(), name='place_create'),
    path('<slug:place_slug>/', place_views.PlaceDetailView.as_view(), name='place_detail'),
    path('<slug:place_slug>/update/', place_views.PlaceUpdateView.as_view(), name='place_update'),
    path('<slug:place_slug>/delete/', place_views.PlaceDeleteView.as_view(), name='place_delete'),
    path('<slug:place_slug>/siteplan/', place_views.siteplan_view, name='siteplan'),
    path('<slug:place_slug>/siteplan/update/', place_views.siteplan_update, name='siteplan_update'),
    path('api/<slug:place_slug>/stats/', place_views.place_stats, name='place_stats_api'),
    # path('<slug:place_slug>/stats/', place_views.place_stats, name='place_stats'),

    # Location URLs
    path('<slug:place_slug>/location/', location_views.LocationListView.as_view(), name='location_list'),
    path('<slug:place_slug>/location/new/', location_views.LocationCreateView.as_view(), name='location_create'),
    path('<slug:place_slug>/location/<slug:slug>/', location_views.LocationDetailView.as_view(), name='location_detail'),
    path('<slug:place_slug>/location/<slug:slug>/update/', location_views.LocationUpdateView.as_view(), name='location_update'),
    path('<slug:place_slug>/location/<slug:slug>/delete/', location_views.LocationDeleteView.as_view(), name='location_delete'),

    # Device URLs
    path('<slug:place_slug>/devices/', device_views.DeviceListView.as_view(), name='device_list'),
    path('<slug:place_slug>/device/create/', device_views.DeviceCreateView.as_view(), name='device_create'),
    path('<slug:place_slug>/location/<slug:location_slug>/device/create/', device_views.DeviceCreateView.as_view(), name='device_create_in_location'),
    path('<slug:place_slug>/device/<int:pk>/', device_views.DeviceDetailView.as_view(), name='device_detail'),
    path('<slug:place_slug>/device/<int:pk>/update/', device_views.DeviceUpdateView.as_view(), name='device_update'),
    path('<slug:place_slug>/device/<int:pk>/delete/', device_views.DeviceDeleteView.as_view(), name='device_delete'),
    path('<slug:place_slug>/device/<int:pk>/fetch-reading/', device_views.fetch_switchbot_reading, name='fetch_switchbot_reading'),
    path('<slug:place_slug>/device/<int:pk>/inspect/', device_views.device_inspect_view, name='device_inspect'),
    path('<slug:place_slug>/device/<int:pk>/add-sensor/', device_views.add_switchbot_sensor, name='add_switchbot_sensor'),

    # Toast URLs
    path('api/<slug:place_slug>/toasts/', toast_views.ToastAPIView.as_view(), name='toast_api'),
    path('<slug:place_slug>/toasts/', toast_views.ToastListView.as_view(), name='toast_list'),

    # Sensor URLs - nested under places, locations, and devices
    path('<slug:place_slug>/device/<int:device_pk>/sensor/create/', SensorCreateView.as_view(), name='sensor_create'),
    path('<slug:place_slug>/device/<int:device_pk>/lorawan-sensor/create/', LoRaWANSensorCreateView.as_view(), name='lorawan_sensor_create'),
    path('<slug:place_slug>/sensors/', SensorListView.as_view(), name='sensor_list'),
    path('<slug:place_slug>/location/<int:location_pk>/sensors/', SensorListView.as_view(), name='location_sensors'),
    path('<slug:place_slug>/device/<int:device_pk>/sensors/', SensorListView.as_view(), name='device_sensors'),
    path('<slug:place_slug>/sensor/<int:pk>/', SensorDetailView.as_view(), name='sensor_detail'),
    path('<slug:place_slug>/sensor/<int:pk>/delta/<str:delta>/', SensorDetailView.as_view(), name='sensor_detail_delta'),
    path('<slug:place_slug>/sensor/<int:pk>/<str:start_date>/<str:end_date>/', SensorDetailView.as_view(), name='sensor_detail_daterange'),
    path('<slug:place_slug>/sensor/<int:pk>/update/', SensorUpdateView.as_view(), name='sensor_update'),
    path('<slug:place_slug>/sensor/<int:pk>/delete/', SensorDeleteView.as_view(), name='sensor_delete'),
    path('<slug:place_slug>/sensor/<int:sensor_pk>/readings/', sensor_views.SensorReadingListView.as_view(), name='sensor_reading_list'),

    # API endpoints for sensor readings
    path('api/<slug:place_slug>/sensor/<int:pk>/update-graph-type/', sensor_views.update_graph_type, name='update_graph_type'),
    path('api/<slug:place_slug>/sensor/<int:pk>/readings/', sensor_views.sensor_readings_api, name='sensor_readings_api'),
    path('api/<slug:place_slug>/sensor/<int:sensor_pk>/readings_table/', sensor_views.sensor_readings_table_api, name='sensor_readings_table_api'),
    path('api/<slug:place_slug>/sensor/<int:pk>/lorawan_data/', sensor_views.lorawan_sensor_data_api, name='lorawan_sensor_data_api'),

    # InfluxSource URLs
    path('<slug:place_slug>/influx-sources/new/', influx_views.InfluxSourceCreateView.as_view(), name='influxsource_create'),
    path('<slug:place_slug>/influx-sources/<int:pk>/', influx_views.InfluxSourceDetailView.as_view(), name='influxsource_detail'),
    path('<slug:place_slug>/influx-sources/<int:pk>/update/', influx_views.InfluxSourceUpdateView.as_view(), name='influxsource_update'),
    path('<slug:place_slug>/influx-sources/<int:pk>/delete/', influx_views.InfluxSourceDeleteView.as_view(), name='influxsource_delete'),

    # Webhook URLs
    # THIS IS NEXT
    path('webhook/switchbot/<slug:place_slug>/', webhook_views.SwitchBotWebhookReceiverView.as_view(), name='switchbot_webhook_receiver'),
    path('webhook/<slug:place_slug>/<uuid:uuid>/', webhook_views.WebhookReceiverView.as_view(), name='webhook_receiver'),

    # Toggle Active State
    path('api/<slug:place_slug>/toggle-active/', toggle_active.ToggleActiveView.as_view(), name='toggle_active'),

    # Timezone
    path('api/set-timezone/', timezone_views.set_user_timezone, name='set_user_timezone'),

    # SensorType URLs
    path('sensortypes/', sensor_type_views.SensorTypeListView.as_view(), name='sensortype_list'),
    path('sensortype/create/', sensor_type_views.SensorTypeCreateView.as_view(), name='sensortype_create'),
    path('sensortype/<int:pk>/', sensor_type_views.SensorTypeDetailView.as_view(), name='sensortype_detail'),
    path('sensortype/<int:pk>/update/', sensor_type_views.SensorTypeUpdateView.as_view(), name='sensortype_update'),
]
