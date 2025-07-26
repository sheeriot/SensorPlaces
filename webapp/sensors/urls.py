from django.urls import path
from .views import (
    place_views, 
    location_views, 
    device_views, 
    sensor_views,
    influx_views,
    webhook_views,
    toggle_active,
)
from .views.sensor_views import (
    SensorListView,
    SensorDetailView,
    SensorCreateView,
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
    path('<slug:place_slug>/siteplan/update', place_views.siteplan_update, name='siteplan_update'),
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
    
    # Sensor URLs - nested under places, locations, and devices
    path('<slug:place_slug>/sensor/create/<int:device_pk>/', SensorCreateView.as_view(), name='sensor_create'),
    path('<slug:place_slug>/lorawan_sensor/create/<int:device_pk>/', sensor_views.LoRaWANSensorCreateView.as_view(), name='lorawan_sensor_create'),
    path('<slug:place_slug>/sensors/', SensorListView.as_view(), name='sensor_list'),
    path('<slug:place_slug>/location/<int:location_pk>/sensors/', SensorListView.as_view(), name='location_sensors'),
    path('<slug:place_slug>/device/<int:device_pk>/sensors/', SensorListView.as_view(), name='device_sensors'),
    path('<slug:place_slug>/sensor/<int:pk>/', SensorDetailView.as_view(), name='sensor_detail'),
    path('<slug:place_slug>/sensor/<int:pk>/update/', SensorUpdateView.as_view(), name='sensor_update'),
    path('<slug:place_slug>/sensor/<int:pk>/delete/', SensorDeleteView.as_view(), name='sensor_delete'),
    path('<slug:place_slug>/sensor/<int:sensor_pk>/readings/', sensor_views.SensorReadingListView.as_view(), name='sensor_reading_list'),

    # InfluxSource URLs
    path('<slug:place_slug>/influx-sources/', influx_views.InfluxSourceListView.as_view(), name='influxsource_list'),
    path('<slug:place_slug>/influx-sources/new/', influx_views.InfluxSourceCreateView.as_view(), name='influxsource_create'),
    path('<slug:place_slug>/influx-sources/<int:pk>/', influx_views.InfluxSourceDetailView.as_view(), name='influxsource_detail'),
    path('<slug:place_slug>/influx-sources/<int:pk>/update/', influx_views.InfluxSourceUpdateView.as_view(), name='influxsource_update'),
    path('<slug:place_slug>/influx-sources/<int:pk>/delete/', influx_views.InfluxSourceDeleteView.as_view(), name='influxsource_delete'),

    # Webhook URLs
    path('webhook/<uuid:uuid>/', webhook_views.WebhookReceiverView.as_view(), name='webhook_receiver'),

    # Toggle Active State
    path('api/<slug:place_slug>/toggle-active/', toggle_active.ToggleActiveView.as_view(), name='toggle_active'),
]
