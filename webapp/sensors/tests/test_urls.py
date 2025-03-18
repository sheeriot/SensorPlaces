from django.test import TestCase, Client
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model
from sensors.models import Place, Location, Device, Sensor, DeviceType
import json

from sensors.views.place_views import (
    PlaceListView, PlaceDetailView, PlaceCreateView, PlaceUpdateView, PlaceDeleteView,
    place_stats, siteplan_update
)
from sensors.views.location_views import (
    LocationListView, LocationDetailView, LocationCreateView, LocationUpdateView, LocationDeleteView
)
from sensors.views.device_views import (
    DeviceListView, DeviceDetailView, DeviceCreateView, DeviceUpdateView, DeviceDeleteView
)
from sensors.views.sensor_views import (
    SensorListView, SensorDetailView, SensorCreateView, SensorUpdateView, SensorDeleteView,
    # SensorReadingListView, SensorReadingDetailView, SensorReadingCreateView, 
    test_sensor_readings
)
from sensors.views.toast_views import ToastAPIView
from sensors.views.toggle_active import ToggleActiveView


class URLResolveTestCase(TestCase):
    """Test that URLs resolve to the correct view functions/classes"""
    
    def test_place_urls_resolve(self):
        """Test place URLs resolve to correct views"""
        self.assertEqual(resolve(reverse('sensors:place_list')).func.view_class, PlaceListView)
        print("===> test_urls.py --> test_place_urls_resolve PASS")
    
    def test_location_urls_resolve(self):
        """Test location URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:location_list', kwargs={'place_slug': 'test-place'})).func.view_class, 
            LocationListView
        )
        print("===> test_urls.py --> test_location_urls_resolve PASS")
    
    def test_device_urls_resolve(self):
        """Test device URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:device_list', kwargs={'place_slug': 'test-place'})).func.view_class, 
            DeviceListView
        )
        print("===> test_urls.py --> test_device_urls_resolve PASS")
    
    def test_sensor_urls_resolve(self):
        """Test sensor URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:sensor_list', kwargs={'place_slug': 'test-place'})).func.view_class, 
            SensorListView
        )
        print("===> test_urls.py --> test_sensor_urls_resolve PASS")
    
    def test_api_urls_resolve(self):
        """Test API URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:toast_api', kwargs={'place_slug': 'test-place'})).func.view_class, 
            ToastAPIView
        )
        print("===> test_urls.py --> test_api_urls_resolve PASS")


class URLAccessTestCase(TestCase):
    """Test access to URLs with authentication and permissions"""
    
    fixtures = [
        'sensors/tests/fixtures/test_users.json',
        'sensors/tests/fixtures/test_places.json',
        'sensors/tests/fixtures/test_locations.json',
        'sensors/tests/fixtures/test_influxsources.json',
        'sensors/tests/fixtures/test_devices.json',
        'sensors/tests/fixtures/test_sensors.json',
        # 'sensors/tests/fixtures/test_readings.json',
    ]
    
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        # Create test data if fixtures are empty
        if not Place.objects.exists():
            self.place = Place.objects.create(
                name='Test Place',
                slug='test-place',
                is_active=True,
                latitude=52.3676,
                longitude=4.9041
            )
        else:
            self.place = Place.objects.first()
            
        if not Location.objects.exists():
            self.location = Location.objects.create(
                name='Test Location',
                place=self.place,
                is_active=True
            )
        else:
            self.location = Location.objects.first()
            
        # Create a device type if none exists
        if not DeviceType.objects.exists():
            self.device_type = DeviceType.objects.create(
                name='Gateway',
                description='Gateway device type for testing',
                icon='bi-router',
                is_active=True
            )
        else:
            self.device_type = DeviceType.objects.first()
            
        if not Device.objects.exists():
            self.device = Device.objects.create(
                name='Test Device',
                location=self.location,
                is_active=True,
                device_type=self.device_type
            )
        else:
            self.device = Device.objects.first()
            
        if not Sensor.objects.exists():
            self.sensor = Sensor.objects.create(
                name='Test Sensor',
                device=self.device,
                is_active=True,
                sensor_type='TEMP',
                unit='°C',
                data_type='API'
            )
        else:
            self.sensor = Sensor.objects.first()
    
    def test_place_list_access(self):
        """Test access to place list view"""
        self.assertEqual(self.client.get(reverse('sensors:place_list')).status_code, 200)
        print("===> test_urls.py --> test_place_list_access PASS")
    
    def test_place_detail_access(self):
        """Test access to place detail view"""
        self.assertEqual(self.client.get(
            reverse('sensors:place_detail', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        print("===> test_urls.py --> test_place_detail_access PASS")
    
    def test_place_create_access(self):
        """Test access to place create view"""
        self.assertEqual(self.client.get(reverse('sensors:place_create')).status_code, 200)
        print("===> test_urls.py --> test_place_create_access PASS")
    
    def test_place_update_access(self):
        """Test access to place update view"""
        self.assertEqual(self.client.get(
            reverse('sensors:place_update', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        print("===> test_urls.py --> test_place_update_access PASS")
    
    def test_location_list_access(self):
        """Test access to location list view"""
        self.assertEqual(self.client.get(
            reverse('sensors:location_list', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        print("===> test_urls.py --> test_location_list_access PASS")
    
    def test_location_detail_access(self):
        """Test access to location detail view"""
        self.assertEqual(self.client.get(
            reverse('sensors:location_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.location.pk
            })
        ).status_code, 200)
        print("===> test_urls.py --> test_location_detail_access PASS")
    
    def test_device_list_access(self):
        """Test access to device list view"""
        self.assertEqual(self.client.get(
            reverse('sensors:device_list', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        print("===> test_urls.py --> test_device_list_access PASS")
    
    def test_device_detail_access(self):
        """Test access to device detail view"""
        self.assertEqual(self.client.get(
            reverse('sensors:device_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.device.pk
            })
        ).status_code, 200)
        print("===> test_urls.py --> test_device_detail_access PASS")
    
    def test_sensor_list_access(self):
        """Test access to sensor list view"""
        self.assertEqual(self.client.get(
            reverse('sensors:sensor_list', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        print("===> test_urls.py --> test_sensor_list_access PASS")
    
    def test_sensor_detail_access(self):
        """Test access to sensor detail view"""
        self.assertEqual(self.client.get(
            reverse('sensors:sensor_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.sensor.pk
            })
        ).status_code, 200)
        print("===> test_urls.py --> test_sensor_detail_access PASS")
    
    def test_api_access(self):
        """Test access to API endpoints"""
        # Test toast API
        self.assertEqual(self.client.get(
            reverse('sensors:toast_api', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        
        # Test toggle active API
        self.assertEqual(self.client.get(
            reverse('sensors:toggle_active', kwargs={'place_slug': self.place.slug})
        ).status_code, 405)  # Should be POST only
        print("===> test_urls.py --> test_api_access PASS")


class FormSubmissionTestCase(TestCase):
    """Test form submissions through views"""
    
    fixtures = [
        'sensors/tests/fixtures/test_users.json',
        'sensors/tests/fixtures/test_places.json',
        'sensors/tests/fixtures/test_locations.json',
        'sensors/tests/fixtures/test_influxsources.json',
        'sensors/tests/fixtures/test_devices.json',
        'sensors/tests/fixtures/test_sensors.json',
        # 'sensors/tests/fixtures/test_readings.json',
    ]
    
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        # Create test data if fixtures are empty
        if not Place.objects.exists():
            self.place = Place.objects.create(
                name='Test Place',
                slug='test-place',
                is_active=True,
                latitude=52.3676,
                longitude=4.9041
            )
        else:
            self.place = Place.objects.first()
            
        if not Location.objects.exists():
            self.location = Location.objects.create(
                name='Test Location',
                place=self.place,
                is_active=True
            )
        else:
            self.location = Location.objects.first()
            
        # Create a device type if none exists
        if not DeviceType.objects.exists():
            self.device_type = DeviceType.objects.create(
                name='Gateway',
                description='Gateway device type for testing',
                icon='bi-router',
                is_active=True
            )
        else:
            self.device_type = DeviceType.objects.first()
            
        if not Device.objects.exists():
            self.device = Device.objects.create(
                name='Test Device',
                location=self.location,
                is_active=True,
                device_type=self.device_type
            )
        else:
            self.device = Device.objects.first()
    
    def test_place_create_form(self):
        """Test creating a place via form submission"""
        place_count = Place.objects.count()
        form_data = {
            'name': 'New Test Place',
            'is_active': True,
            'latitude': 51.5074,
            'longitude': -0.1278
        }
        try:
            response = self.client.post(
                reverse('sensors:place_create'),
                form_data
            )
            
            if response.status_code != 302:
                if hasattr(response, 'context') and response.context and 'form' in response.context:
                    form_errors = response.context['form'].errors
                    print(f"Form errors: {form_errors}")
                    raise AssertionError(f"Expected redirect (302), got {response.status_code}. Form errors: {form_errors}")
                else:
                    raise AssertionError(f"Expected redirect (302), got {response.status_code}")
                
            new_place = Place.objects.latest('id')
            self.assertEqual(new_place.name, 'New Test Place')
            self.assertTrue(new_place.is_active)
            print("===> test_urls.py --> test_place_create_form PASS")
        except Exception as e:
            print(f"===> test_urls.py --> test_place_create_form FAIL: {str(e)}")
            raise
    
    def test_location_create_form(self):
        """Test creating a location via form submission"""
        location_count = Location.objects.count()
        form_data = {
            'name': 'New Test Location',
            'place': self.place.id,
            'is_active': True
        }
        self.assertEqual(self.client.post(
            reverse('sensors:location_create', kwargs={'place_slug': self.place.slug}),
            form_data
        ).status_code, 302)
        self.assertEqual(Location.objects.count(), location_count + 1)
        self.assertEqual(Location.objects.latest('id').name, 'New Test Location')
        self.assertTrue(Location.objects.latest('id').is_active)
        print("===> test_urls.py --> test_location_create_form PASS")
    
    def test_device_create_form(self):
        """Test creating a device via form submission"""
        device_count = Device.objects.count()
        form_data = {
            'name': 'New Test Device',
            'location': self.location.id,
            'is_active': True,
            'device_type': self.device_type.id,
            'manufacturer': 'Test Manufacturer',
            'model': 'Test Model',
            'serial_number': 'TEST123'
        }
        self.assertEqual(self.client.post(
            reverse('sensors:device_create', kwargs={
                'place_slug': self.place.slug,
                'location_pk': self.location.pk
            }),
            form_data
        ).status_code, 302)
        self.assertEqual(Device.objects.count(), device_count + 1)
        self.assertEqual(Device.objects.latest('id').name, 'New Test Device')
        self.assertTrue(Device.objects.latest('id').is_active)
        print("===> test_urls.py --> test_device_create_form PASS")
    
    def test_sensor_create_form(self):
        """Test creating a sensor via form submission"""
        sensor_count = Sensor.objects.count()
        
        # Make the device active for the test
        if not self.device.is_active:
            self.device.is_active = True
            self.device.save()
        
        form_data = {
            'name': 'New Test Sensor',
            'device': self.device.id,
            'is_active': True,  # Set to True to match our test expectation
            'sensor_type': 'TEMP',
            'unit': '°C',
            'data_type': 'DB',
            'influx_measurement': 'test_measurement',
            'referrer': '',
        }
        
        url = reverse('sensors:sensor_create', kwargs={
            'place_slug': self.place.slug,
            'device_pk': self.device.pk
        })
        
        self.assertEqual(self.client.post(url, form_data).status_code, 302)
        self.assertEqual(Sensor.objects.count(), sensor_count + 1)
        self.assertEqual(Sensor.objects.latest('id').name, 'New Test Sensor')
        self.assertTrue(Sensor.objects.latest('id').is_active)
        print("===> test_urls.py --> test_sensor_create_form PASS")
    
    def test_toggle_active_api(self):
        """Test toggling active status via API for a device with dependent sensors"""
        # Create a test hierarchy explicitly for this test
        # Create a test place
        place = Place.objects.create(
            name='Toggle Test Place',
            slug='toggle-test-place',
            is_active=True,
            latitude=51.5074,
            longitude=-0.1278
        )
        
        # Create a test location
        location = Location.objects.create(
            name='Toggle Test Location',
            place=place,
            is_active=True
        )
        
        # Create a device type
        device_type = DeviceType.objects.create(
            name='Toggle Test Type',
            description='Test device type for toggle API test',
            icon='bi-router',
            is_active=True
        )
        
        # Create a test device
        device = Device.objects.create(
            name='Toggle Test Device',
            location=location,
            is_active=True,
            device_type=device_type
        )
        
        # Create sensors for this device
        sensors = []
        for i in range(4):
            sensor = Sensor.objects.create(
                name=f'Toggle Test Sensor {i+1}',
                device=device,
                is_active=True,
                sensor_type='TEMP',
                unit='°C',
                data_type='DB'
            )
            sensors.append(sensor)
        
        # Get CSRF token
        response = self.client.get(reverse('sensors:place_detail', kwargs={'place_slug': place.slug}))
        csrf_token = self.client.cookies.get('csrftoken')
        csrf_value = csrf_token.value if csrf_token else ''
        
        # Test deactivating the device
        data = {
            'model_type': 'device',
            'id': device.pk,
            'is_active': False,
            'csrf_token': csrf_value
        }
        
        response = self.client.post(
            reverse('sensors:toggle_active', kwargs={'place_slug': place.slug}),
            json.dumps(data),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_value
        )
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertFalse(response_data['is_active'])
        
        # Verify dependencies in response
        self.assertIn('dependencies', response_data)
        self.assertEqual(len(response_data['dependencies']), len(sensors))
        
        # Refresh from database and check device state
        device.refresh_from_db()
        self.assertFalse(device.is_active)
        
        # Check that all sensors were also deactivated
        for sensor in sensors:
            sensor.refresh_from_db()
            self.assertFalse(sensor.is_active, f"Sensor {sensor.name} should have been deactivated")
        
        # Now toggle it back to active
        data = {
            'model_type': 'device',
            'id': device.pk,
            'is_active': True,
            'csrf_token': csrf_value
        }
        
        response = self.client.post(
            reverse('sensors:toggle_active', kwargs={'place_slug': place.slug}),
            json.dumps(data),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_value
        )
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertTrue(response_data['is_active'])
        
        # Refresh from database and check device state
        device.refresh_from_db()
        self.assertTrue(device.is_active)
        
        print("===> test_urls.py --> test_toggle_active_api PASS") 