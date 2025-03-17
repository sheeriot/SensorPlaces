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
        self.assertEqual(resolve(reverse('sensors:place_create')).func.view_class, PlaceCreateView)
        self.assertEqual(
            resolve(reverse('sensors:place_detail', kwargs={'place_slug': 'test-place'})).func.view_class, 
            PlaceDetailView
        )
        self.assertEqual(
            resolve(reverse('sensors:place_update', kwargs={'place_slug': 'test-place'})).func.view_class, 
            PlaceUpdateView
        )
        self.assertEqual(
            resolve(reverse('sensors:place_delete', kwargs={'place_slug': 'test-place'})).func.view_class, 
            PlaceDeleteView
        )
        self.assertEqual(
            resolve(reverse('sensors:place_stats', kwargs={'place_slug': 'test-place'})).func, 
            place_stats
        )
        self.assertEqual(
            resolve(reverse('sensors:siteplan_update', kwargs={'place_slug': 'test-place'})).func, 
            siteplan_update
        )
    
    def test_location_urls_resolve(self):
        """Test location URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:location_list', kwargs={'place_slug': 'test-place'})).func.view_class, 
            LocationListView
        )
        self.assertEqual(
            resolve(reverse('sensors:location_create', kwargs={'place_slug': 'test-place'})).func.view_class, 
            LocationCreateView
        )
        self.assertEqual(
            resolve(reverse('sensors:location_detail', kwargs={'place_slug': 'test-place', 'pk': 1})).func.view_class, 
            LocationDetailView
        )
        self.assertEqual(
            resolve(reverse('sensors:location_update', kwargs={'place_slug': 'test-place', 'pk': 1})).func.view_class, 
            LocationUpdateView
        )
        self.assertEqual(
            resolve(reverse('sensors:location_delete', kwargs={'place_slug': 'test-place', 'pk': 1})).func.view_class, 
            LocationDeleteView
        )
    
    def test_device_urls_resolve(self):
        """Test device URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:device_list', kwargs={'place_slug': 'test-place'})).func.view_class, 
            DeviceListView
        )
        self.assertEqual(
            resolve(reverse('sensors:device_create', kwargs={'place_slug': 'test-place', 'location_pk': 1})).func.view_class, 
            DeviceCreateView
        )
        self.assertEqual(
            resolve(reverse('sensors:device_create_choose_location', kwargs={'place_slug': 'test-place'})).func.view_class, 
            DeviceCreateView
        )
        self.assertEqual(
            resolve(reverse('sensors:location_devices', kwargs={'place_slug': 'test-place', 'location_pk': 1})).func.view_class, 
            DeviceListView
        )
        self.assertEqual(
            resolve(reverse('sensors:device_detail', kwargs={'place_slug': 'test-place', 'pk': 1})).func.view_class, 
            DeviceDetailView
        )
        self.assertEqual(
            resolve(reverse('sensors:device_update', kwargs={'place_slug': 'test-place', 'pk': 1})).func.view_class, 
            DeviceUpdateView
        )
        self.assertEqual(
            resolve(reverse('sensors:device_delete', kwargs={'place_slug': 'test-place', 'pk': 1})).func.view_class, 
            DeviceDeleteView
        )
    
    def test_sensor_urls_resolve(self):
        """Test sensor URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:sensor_list', kwargs={'place_slug': 'test-place'})).func.view_class, 
            SensorListView
        )
        self.assertEqual(
            resolve(reverse('sensors:sensor_create', kwargs={'place_slug': 'test-place', 'device_pk': 1})).func.view_class, 
            SensorCreateView
        )
        self.assertEqual(
            resolve(reverse('sensors:location_sensors', kwargs={'place_slug': 'test-place', 'location_pk': 1})).func.view_class, 
            SensorListView
        )
        self.assertEqual(
            resolve(reverse('sensors:device_sensors', kwargs={'place_slug': 'test-place', 'device_pk': 1})).func.view_class, 
            SensorListView
        )
        self.assertEqual(
            resolve(reverse('sensors:sensor_detail', kwargs={'place_slug': 'test-place', 'pk': 1})).func.view_class, 
            SensorDetailView
        )
        self.assertEqual(
            resolve(reverse('sensors:sensor_update', kwargs={'place_slug': 'test-place', 'pk': 1})).func.view_class, 
            SensorUpdateView
        )
        self.assertEqual(
            resolve(reverse('sensors:sensor_delete', kwargs={'place_slug': 'test-place', 'pk': 1})).func.view_class, 
            SensorDeleteView
        )
        self.assertEqual(
            resolve(reverse('sensors:sensor_test', kwargs={'place_slug': 'test-place', 'pk': 1})).func, 
            test_sensor_readings
        )
    
    # def test_reading_urls_resolve(self):
    #     """Test sensor reading URLs resolve to correct views"""
    #     self.assertEqual(
    #         resolve(reverse('sensors:place_readings', kwargs={'place_slug': 'test-place'})).func.view_class, 
    #         SensorReadingListView
    #     )
    #     self.assertEqual(
    #         resolve(reverse('sensors:reading_detail', kwargs={'place_slug': 'test-place', 'pk': 1})).func.view_class, 
    #         SensorReadingDetailView
    #     )
    #     self.assertEqual(
    #         resolve(reverse('sensors:reading_create', kwargs={'place_slug': 'test-place'})).func.view_class, 
    #         SensorReadingCreateView
    #     )
    
    def test_api_urls_resolve(self):
        """Test API URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:toast_api', kwargs={'place_slug': 'test-place'})).func.view_class, 
            ToastAPIView
        )
        self.assertEqual(
            resolve(reverse('sensors:toggle_active', kwargs={'place_slug': 'test-place'})).func.view_class, 
            ToggleActiveView
        )


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
        response = self.client.get(reverse('sensors:place_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_place_detail_access(self):
        """Test access to place detail view"""
        response = self.client.get(
            reverse('sensors:place_detail', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
    
    def test_place_create_access(self):
        """Test access to place create view"""
        response = self.client.get(reverse('sensors:place_create'))
        self.assertEqual(response.status_code, 200)
    
    def test_place_update_access(self):
        """Test access to place update view"""
        response = self.client.get(
            reverse('sensors:place_update', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
    
    def test_location_list_access(self):
        """Test access to location list view"""
        response = self.client.get(
            reverse('sensors:location_list', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
    
    def test_location_detail_access(self):
        """Test access to location detail view"""
        response = self.client.get(
            reverse('sensors:location_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.location.pk
            })
        )
        self.assertEqual(response.status_code, 200)
    
    def test_device_list_access(self):
        """Test access to device list view"""
        response = self.client.get(
            reverse('sensors:device_list', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
    
    def test_device_detail_access(self):
        """Test access to device detail view"""
        response = self.client.get(
            reverse('sensors:device_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.device.pk
            })
        )
        self.assertEqual(response.status_code, 200)
    
    def test_sensor_list_access(self):
        """Test access to sensor list view"""
        response = self.client.get(
            reverse('sensors:sensor_list', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
    
    def test_sensor_detail_access(self):
        """Test access to sensor detail view"""
        response = self.client.get(
            reverse('sensors:sensor_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.sensor.pk
            })
        )
        self.assertEqual(response.status_code, 200)
    
    def test_api_access(self):
        """Test access to API endpoints"""
        # Test toast API
        response = self.client.get(
            reverse('sensors:toast_api', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        
        # Test toggle active API
        response = self.client.get(
            reverse('sensors:toggle_active', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 405)  # Should be POST only


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
        print("Starting test_place_create_form")
        form_data = {
            'name': 'New Test Place',
            'is_active': True,
            'latitude': 51.5074,
            'longitude': -0.1278
        }
        print(f"Form data being submitted: {form_data}")
        response = self.client.post(
            reverse('sensors:place_create'),
            form_data
        )
        print(f"Response status code: {response.status_code}")
        if response.status_code != 302:
            if hasattr(response, 'context') and response.context and 'form' in response.context:
                print(f"Form errors: {response.context['form'].errors}")
                print(f"Form fields: {response.context['form'].fields.keys()}")
            else:
                print("No form in response context")
        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)
        # Check that a new place was created
        self.assertEqual(Place.objects.count(), place_count + 1)
        # Check that the new place has the correct data
        new_place = Place.objects.latest('id')
        self.assertEqual(new_place.name, 'New Test Place')
        self.assertTrue(new_place.is_active)
    
    def test_location_create_form(self):
        """Test creating a location via form submission"""
        print("\nStarting test_location_create_form")
        location_count = Location.objects.count()
        form_data = {
            'name': 'New Test Location',
            'place': self.place.id,
            'is_active': True
        }
        print(f"Location form data: {form_data}")
        response = self.client.post(
            reverse('sensors:location_create', kwargs={'place_slug': self.place.slug}),
            form_data
        )
        print(f"Location create response status: {response.status_code}")
        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)
        # Check that a new location was created
        self.assertEqual(Location.objects.count(), location_count + 1)
        # Check that the new location has the correct data
        new_location = Location.objects.latest('id')
        self.assertEqual(new_location.name, 'New Test Location')
        self.assertTrue(new_location.is_active)
        print("Completed test_location_create_form")
    
    def test_device_create_form(self):
        """Test creating a device via form submission"""
        print("\nStarting test_device_create_form")
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
        print(f"Device form data: {form_data}")
        response = self.client.post(
            reverse('sensors:device_create', kwargs={
                'place_slug': self.place.slug,
                'location_pk': self.location.pk
            }),
            form_data
        )
        print(f"Device create response status: {response.status_code}")
        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)
        # Check that a new device was created
        self.assertEqual(Device.objects.count(), device_count + 1)
        # Check that the new device has the correct data
        new_device = Device.objects.latest('id')
        self.assertEqual(new_device.name, 'New Test Device')
        self.assertTrue(new_device.is_active)
        print("Completed test_device_create_form")
    
    def test_sensor_create_form(self):
        """Test creating a sensor via form submission"""
        sensor_count = Sensor.objects.count()
        
        # Ensure we have a valid device
        # print(f"Using device: {self.device.name} (ID: {self.device.id})")
        # print(f"Device location: {self.device.location.name} (ID: {self.device.location.id})")
        # print(f"Location place: {self.device.location.place.name} (ID: {self.device.location.place.id})")
        # print(f"Device is_active: {self.device.is_active}")
        
        # Make the device active for the test
        if not self.device.is_active:
            # print("Activating device for test")
            self.device.is_active = True
            self.device.save()
            # print(f"Device is now active: {self.device.is_active}")
        
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
        # print(f"Posting to URL: {url}")
        
        response = self.client.post(url, form_data)
        
        # If the response is not a redirect, print form errors
        if response.status_code != 302:
            # print(f"Form submission failed with status code: {response.status_code}")
            if hasattr(response, 'context') and response.context and 'form' in response.context:
                # print(f"Form errors: {response.context['form'].errors}")
                pass
            else:
                # print("No form in response context")
                pass
        
        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)
        # Check that a new sensor was created
        self.assertEqual(Sensor.objects.count(), sensor_count + 1)
        # Check that the new sensor has the correct data
        new_sensor = Sensor.objects.latest('id')
        self.assertEqual(new_sensor.name, 'New Test Sensor')
        self.assertTrue(new_sensor.is_active)
        # print(f"Created sensor: {new_sensor.name}, is_active: {new_sensor.is_active}")
    
    def test_toggle_active_api(self):
        """Test toggling active status via API"""
        # Test toggling a place
        initial_status = self.place.is_active
        
        print(f"Initial place active status: {initial_status}")
        print(f"CSRF token before get: {self.client.cookies.get('csrftoken')}")
        
        # First get the CSRF token
        self.client.get(reverse('sensors:place_detail', kwargs={'place_slug': self.place.slug}))
        
        print(f"CSRF token after get: {self.client.cookies.get('csrftoken')}")
        
        # Check if csrftoken is a string or has a value attribute
        csrf_token = self.client.cookies.get('csrftoken')
        print(f"CSRF token type: {type(csrf_token)}")
        
        # Fix the issue with csrf_token value
        if csrf_token is None:
            csrf_value = ''
            print("No CSRF token found")
        elif isinstance(csrf_token, str):
            csrf_value = csrf_token
            print(f"CSRF token is a string: {csrf_value}")
        else:
            csrf_value = csrf_token.value
            print(f"CSRF token has value attribute: {csrf_value}")
        
        data = {
            'model_type': 'place',
            'object_id': self.place.id,
            'is_active': not initial_status,
            'csrf_token': csrf_value
        }
        
        print(f"Request data: {data}")
        
        response = self.client.post(
            reverse('sensors:toggle_active', kwargs={'place_slug': self.place.slug}),
            json.dumps(data),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_value
        )
        
        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.content.decode()}")
        
        # If the API returns 400, let's check the response content for debugging
        if response.status_code == 400:
            print(f"API Error Response: {response.content.decode()}")
            # Try with a different format
            data = {
                'model_type': 'place',
                'id': self.place.id,
                'active': not initial_status
            }
            print(f"Retrying with data: {data}")
            response = self.client.post(
                reverse('sensors:toggle_active', kwargs={'place_slug': self.place.slug}),
                json.dumps(data),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_value
            )
            print(f"Second response status code: {response.status_code}")
            print(f"Second response content: {response.content.decode()}")
        
        # Accept either 200 or 302 as success
        self.assertIn(response.status_code, [200, 302])
        
        # Refresh from database
        self.place.refresh_from_db()
        print(f"Place active status after API call: {self.place.is_active}")
        
        # Check that status was toggled - only if the API call was successful
        if response.status_code in [200, 302]:
            self.assertEqual(self.place.is_active, not initial_status) 