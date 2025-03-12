from django.urls import path
from . import views

app_name = 'sensors'

urlpatterns = [
    # Place URLs
    path('', views.PlaceListView.as_view(), name='place_list'),
    path('place/create/', views.PlaceCreateView.as_view(), name='place_create'),
    path('<slug:place_slug>/', views.PlaceDetailView.as_view(), name='place_detail'),
    path('<slug:place_slug>/update/', views.PlaceUpdateView.as_view(), name='place_update'),
    path('<slug:place_slug>/delete/', views.PlaceDeleteView.as_view(), name='place_delete'),
    
    # Location URLs - nested under places
    path('<slug:place_slug>/location/create/', views.LocationCreateView.as_view(), name='location_create'),
    path('<slug:place_slug>/locations/', views.LocationListView.as_view(), name='location_list'),
    path('<slug:place_slug>/location/<int:pk>/', views.LocationDetailView.as_view(), name='location_detail'),
    path('<slug:place_slug>/location/<int:pk>/update/', views.LocationUpdateView.as_view(), name='location_update'),
    path('<slug:place_slug>/location/<int:pk>/delete/', views.LocationDeleteView.as_view(), name='location_delete'),
    
    # Device URLs - nested under places and locations
    path('<slug:place_slug>/location/<int:location_pk>/device/create/', views.DeviceCreateView.as_view(), name='device_create'),
    
    # New URL pattern for when location needs to be selected
    path('<slug:place_slug>/device/create/', views.DeviceCreateView.as_view(), name='device_create_choose_location'),
    
    # Device URLs - nested under device
    path('<slug:place_slug>/devices/', views.DeviceListView.as_view(), name='device_list'),
    path('<slug:place_slug>/location/<int:location_pk>/devices/', views.DeviceListView.as_view(), name='location_devices'),
    
    path('<slug:place_slug>/device/<int:pk>/', views.DeviceDetailView.as_view(), name='device_detail'),
    path('<slug:place_slug>/device/<int:pk>/update/', views.DeviceUpdateView.as_view(), name='device_update'),
    path('<slug:place_slug>/device/<int:pk>/delete/', views.DeviceDeleteView.as_view(), name='device_delete'),
    
    # Sensor URLs - nested under places, locations, and devices
    path('<slug:place_slug>/device/<int:device_pk>/sensor/create/', views.SensorCreateView.as_view(), name='sensor_create'),
    
    path('<slug:place_slug>/sensors/', views.SensorListView.as_view(), name='sensor_list'),
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
    path('api/<slug:place_slug>/siteplan_update/', views.siteplan_update, name='siteplan_update'),

    # New consolidated toggle active endpoint
    path('api/<slug:place_slug>/toggle_active/<str:model>/<int:pk>/', views.ToggleActiveView.as_view(), name='toggle_active'),

    # path('api/<slug:place_slug>/device/<int:pk>/active_sensors/', views.DeviceActiveSensorsView.as_view(), name='device_active_sensors'),
    path('api/<slug:place_slug>/device/<int:pk>/move_location/', views.DeviceMoveLocationView.as_view(), name='device_move_location'),
    
    path('api/<slug:place_slug>/sensor_test/<int:pk>', views.test_sensor_readings, name='sensor_test'),
    path('api/toast-history/', views.ToastHistoryView.as_view(), name='toast_history'),
    path('api/toast-history/<slug:place_slug>/', views.ToastHistoryView.as_view(), name='place_toast_history'),
    path('api/toast-read/', views.mark_toast_read, name='mark_toast_read'),
    path('api/toast-clear/', views.clear_toast_history, name='clear_toast_history'),
    path('api/toast-clear/<slug:place_slug>/', views.clear_toast_history, name='clear_place_toast_history'),
]
