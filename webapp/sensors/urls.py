from django.urls import path
from . import views

app_name = 'sensors'

urlpatterns = [
    # Place URLs
    path('', views.PlaceListView.as_view(), name='place_list'),
    path('create/', views.PlaceCreateView.as_view(), name='place_create'),
    path('<slug:place_slug>/', views.PlaceDetailView.as_view(), name='place_detail'),
    path('<slug:place_slug>/update/', views.PlaceUpdateView.as_view(), name='place_update'),
    path('<slug:place_slug>/delete/', views.PlaceDeleteView.as_view(), name='place_delete'),

    path('<slug:place_slug>/update_site_plan_layout/', views.update_site_plan_layout, name='update_site_plan_layout'),
    
    # Location URLs - nested under places
    path('<slug:place_slug>/location/create/', views.LocationCreateView.as_view(), name='location_create'),
    path('<slug:place_slug>/locations/', views.LocationListView.as_view(), name='place_locations'),
    path('<slug:place_slug>/location/<int:pk>/', views.LocationDetailView.as_view(), name='location_detail'),

    path('<slug:place_slug>/location/<int:pk>/update/', views.LocationUpdateView.as_view(), name='location_update'),
    path('<slug:place_slug>/location/<int:pk>/delete/', views.LocationDeleteView.as_view(), name='location_delete'),
    path('<slug:place_slug>/location/<int:pk>/position/', views.location_update_position, name='location_update_position'),
    
    # Device URLs - nested under places and locations
    path('<slug:place_slug>/location/<int:location_pk>/device/create/', views.DeviceCreateView.as_view(), name='device_create'),
    
    # Device URLs - nested under device
    path('<slug:place_slug>/devices/', views.DeviceListView.as_view(), name='place_devices'),
    path('<slug:place_slug>/location/<int:location_pk>/devices/', views.DeviceListView.as_view(), name='location_devices'),
    
    path('<slug:place_slug>/device/<int:pk>/', views.DeviceDetailView.as_view(), name='device_detail'),
    path('<slug:place_slug>/device/<int:pk>/update/', views.DeviceUpdateView.as_view(), name='device_update'),
    path('<slug:place_slug>/device/<int:pk>/delete/', views.DeviceDeleteView.as_view(), name='device_delete'),
    
    # Sensor URLs - nested under places, locations, and devices
    path('<slug:place_slug>/device/<int:pk>/sensor/create/', views.SensorCreateView.as_view(), name='sensor_create'),
    
    path('<slug:place_slug>/sensors/', views.SensorListView.as_view(), name='place_sensors'),
    path('<slug:place_slug>/location/<int:location_pk>/sensors/', views.SensorListView.as_view(), name='location_sensors'),
    path('<slug:place_slug>/device/<int:device_pk>/sensors/', views.SensorListView.as_view(), name='device_sensors'),

    path('<slug:place_slug>/sensor/<int:pk>/', views.SensorDetailView.as_view(), name='sensor_detail'),
    path('<slug:place_slug>/sensor/<int:pk>/update/', views.SensorUpdateView.as_view(), name='sensor_update'),
    path('<slug:place_slug>/sensor/<int:pk>/delete/', views.SensorDeleteView.as_view(), name='sensor_delete'),

    # Reading URLs - nested under places
    path('<slug:place_slug>/readings/', views.SensorReadingListView.as_view(), name='place_readings'),
    path('<slug:place_slug>/readings/<int:pk>/', views.SensorReadingDetailView.as_view(), name='reading_detail'),
    path('<slug:place_slug>/readings/create/', views.SensorReadingCreateView.as_view(), name='reading_create'),
    
    # API URLs
    path('api/<slug:place_slug>/stats/', views.place_stats, name='place_stats'),
    path('api/<slug:place_slug>/locations/<int:pk>/position/', views.location_update_position, name='location_update_position'),
    path('api/<slug:place_slug>/sensors/<int:pk>/toggle_active/', views.sensor_toggle_active, name='sensor_toggle_active'),
    path('api/<slug:place_slug>/device/<int:pk>/toggle_active/', views.DeviceToggleActiveView.as_view(), name='device_toggle_active'),
    path('api/<slug:place_slug>/device/<int:pk>/move_location/', views.DeviceMoveLocationView.as_view(), name='device_move_location'),
    path('api/<slug:place_slug>/sensor_test/<int:sensor_pk>', views.test_sensor_readings, name='sensor_test'),
    path('api/<slug:place_slug>/location/<int:pk>/toggle_active/', views.location_toggle_active, name='location_toggle_active'),
]
