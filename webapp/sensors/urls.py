from django.urls import path
from .views.place_views import (
    PlaceListView, PlaceDetailView, PlaceCreateView, PlaceUpdateView, PlaceDeleteView,
    place_stats, siteplan_update
)
from .views.location_views import (
    LocationListView, LocationDetailView, LocationCreateView, LocationUpdateView, LocationDeleteView
)
from .views.device_views import (
    DeviceListView, DeviceDetailView, DeviceCreateView, DeviceUpdateView, DeviceDeleteView,
    # DeviceMoveLocationView
)
from .views.sensor_views import (
    SensorListView, SensorDetailView, SensorCreateView, SensorUpdateView, SensorDeleteView,
    SensorReadingListView, SensorReadingDetailView, SensorReadingCreateView, test_sensor_readings
)
from .views.toast_views import ToastAPIView, ToastListView
from .views.toggle_active import ToggleActiveView

app_name = 'sensors'

urlpatterns = [

    # Shared API endpoints
    path('api/<slug:place_slug>/toasts/', ToastAPIView.as_view(), name='toast_api'),
    path('api/<slug:place_slug>/toggle-active/', ToggleActiveView.as_view(), name='toggle_active'),

    # Toast URLs
    path('<slug:place_slug>/notifications/', ToastListView.as_view(), name='toast_list'),
    
    # Place URLs
    path('', PlaceListView.as_view(), name='place_list'),
    path('place/create/', PlaceCreateView.as_view(), name='place_create'),
    path('<slug:place_slug>/', PlaceDetailView.as_view(), name='place_detail'),
    path('<slug:place_slug>/update/', PlaceUpdateView.as_view(), name='place_update'),
    path('<slug:place_slug>/delete/', PlaceDeleteView.as_view(), name='place_delete'),
    # Place API URLs
    path('api/<slug:place_slug>/stats/', place_stats, name='place_stats'),
    path('api/<slug:place_slug>/siteplan_update/', siteplan_update, name='siteplan_update'),
    
    # Location URLs - nested under places
    path('<slug:place_slug>/location/create/', LocationCreateView.as_view(), name='location_create'),
    path('<slug:place_slug>/locations/', LocationListView.as_view(), name='location_list'),
    path('<slug:place_slug>/location/<int:pk>/', LocationDetailView.as_view(), name='location_detail'),
    path('<slug:place_slug>/location/<int:pk>/update/', LocationUpdateView.as_view(), name='location_update'),
    path('<slug:place_slug>/location/<int:pk>/delete/', LocationDeleteView.as_view(), name='location_delete'),
    
    # Device URLs - nested under places and locations
    path('<slug:place_slug>/location/<int:location_pk>/device/create/', DeviceCreateView.as_view(), name='device_create'),
    path('<slug:place_slug>/device/create/', DeviceCreateView.as_view(), name='device_create_choose_location'),
    path('<slug:place_slug>/devices/', DeviceListView.as_view(), name='device_list'),
    path('<slug:place_slug>/location/<int:location_pk>/devices/', DeviceListView.as_view(), name='location_devices'),
    path('<slug:place_slug>/device/<int:pk>/', DeviceDetailView.as_view(), name='device_detail'),
    path('<slug:place_slug>/device/<int:pk>/update/', DeviceUpdateView.as_view(), name='device_update'),
    path('<slug:place_slug>/device/<int:pk>/delete/', DeviceDeleteView.as_view(), name='device_delete'),
    # Device APIs
    # path('api/<slug:place_slug>/device/<int:pk>/move_location/', DeviceMoveLocationView.as_view(), name='device_move_location'),
    
    # Sensor URLs - nested under places, locations, and devices
    path('<slug:place_slug>/device/<int:device_pk>/sensor/create/', SensorCreateView.as_view(), name='sensor_create'),
    path('<slug:place_slug>/sensors/', SensorListView.as_view(), name='sensor_list'),
    path('<slug:place_slug>/location/<int:location_pk>/sensors/', SensorListView.as_view(), name='location_sensors'),
    path('<slug:place_slug>/device/<int:device_pk>/sensors/', SensorListView.as_view(), name='device_sensors'),
    path('<slug:place_slug>/sensor/<int:pk>/', SensorDetailView.as_view(), name='sensor_detail'),
    path('<slug:place_slug>/sensor/<int:pk>/update/', SensorUpdateView.as_view(), name='sensor_update'),
    path('<slug:place_slug>/sensor/<int:pk>/delete/', SensorDeleteView.as_view(), name='sensor_delete'),
    path('api/<slug:place_slug>/sensor_test/<int:pk>', test_sensor_readings, name='sensor_test'),

    # Sensor `Reading URLs - nested under places
    path('<slug:place_slug>/readings/', SensorReadingListView.as_view(), name='place_readings'),
    path('<slug:place_slug>/readings/<int:pk>/', SensorReadingDetailView.as_view(), name='reading_detail'),
    path('<slug:place_slug>/readings/create/', SensorReadingCreateView.as_view(), name='reading_create'),

]
