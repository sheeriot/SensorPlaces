from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from sensors.models import Place, Location, Device, Sensor, DeviceType
from django.core.files.uploadedfile import SimpleUploadedFile
import json
import os

class SensorsViewTestCase(TestCase):
    # Specify the full path to fixtures
    fixtures = [
        'sensors/tests/fixtures/test_users.json',
        'sensors/tests/fixtures/test_places.json',
        'sensors/tests/fixtures/test_locations.json',
        'sensors/tests/fixtures/test_devices.json',
        'sensors/tests/fixtures/test_influxsources.json',
        'sensors/tests/fixtures/test_sensors.json',
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
                data_type='DB'
            )
        else:
            self.sensor = Sensor.objects.first()

    # Place View Tests
    def test_place_list_view(self):
        """Test PlaceListView displays correctly"""
        response = self.client.get(reverse('sensors:place_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/place_list.html')
        self.assertContains(response, self.place.name)

    def test_place_detail_view(self):
        """Test PlaceDetailView displays correctly"""
        response = self.client.get(
            reverse('sensors:place_detail', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/place_detail.html')
        self.assertContains(response, self.place.name)
    
    def test_place_create_view(self):
        """Test PlaceCreateView displays correctly"""
        response = self.client.get(reverse('sensors:place_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/place_form.html')
        self.assertContains(response, 'Create New Place')
    
    def test_place_update_view(self):
        """Test PlaceUpdateView displays correctly"""
        response = self.client.get(
            reverse('sensors:place_update', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/place_form.html')
        self.assertContains(response, 'Update Place')
    
    def test_place_delete_view(self):
        """Test PlaceDeleteView displays correctly"""
        response = self.client.get(
            reverse('sensors:place_delete', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/place_confirm_delete.html')
        self.assertContains(response, 'Delete Place')
    
    def test_place_create_post(self):
        """Test creating a place via POST request"""
        place_count = Place.objects.count()
        response = self.client.post(
            reverse('sensors:place_create'),
            {
                'name': 'New Test Place',
                'is_active': True,
                'latitude': 51.5074,
                'longitude': -0.1278
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        self.assertEqual(Place.objects.count(), place_count + 1)
        new_place = Place.objects.latest('id')
        self.assertEqual(new_place.name, 'New Test Place')
    
    def test_place_update_post(self):
        """Test updating a place via POST request"""
        response = self.client.post(
            reverse('sensors:place_update', kwargs={'place_slug': self.place.slug}),
            {
                'name': 'Updated Place Name',
                'is_active': self.place.is_active,
                'latitude': self.place.latitude,
                'longitude': self.place.longitude
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        self.place.refresh_from_db()
        self.assertEqual(self.place.name, 'Updated Place Name')
    
    def test_place_delete_post(self):
        """Test deleting a place via POST request"""
        # Create a temporary place to delete
        temp_place = Place.objects.create(
            name='Temp Place',
            slug='temp-place',
            is_active=True,
            latitude=40.7128,
            longitude=-74.0060
        )
        place_count = Place.objects.count()
        response = self.client.post(
            reverse('sensors:place_delete', kwargs={'place_slug': temp_place.slug}),
            {'confirm_name': temp_place.name}
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        self.assertEqual(Place.objects.count(), place_count - 1)
        with self.assertRaises(Place.DoesNotExist):
            Place.objects.get(slug='temp-place')
    
    # Location View Tests
    def test_location_list_view(self):
        """Test LocationListView displays correctly"""
        response = self.client.get(
            reverse('sensors:location_list', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/location_list.html')
        self.assertContains(response, self.location.name)
    
    def test_location_detail_view(self):
        """Test LocationDetailView displays correctly"""
        response = self.client.get(
            reverse('sensors:location_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.location.pk
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/location_detail.html')
        self.assertContains(response, self.location.name)
    
    def test_location_create_view(self):
        """Test LocationCreateView displays correctly"""
        response = self.client.get(
            reverse('sensors:location_create', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/location_form.html')
        self.assertContains(response, 'Create New Location')
    
    def test_location_update_view(self):
        """Test LocationUpdateView displays correctly"""
        response = self.client.get(
            reverse('sensors:location_update', kwargs={
                'place_slug': self.place.slug,
                'pk': self.location.pk
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/location_form.html')
        self.assertContains(response, 'Update Location')
    
    def test_location_delete_view(self):
        """Test LocationDeleteView displays correctly"""
        response = self.client.get(
            reverse('sensors:location_delete', kwargs={
                'place_slug': self.place.slug,
                'pk': self.location.pk
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/location_confirm_delete.html')
        self.assertContains(response, 'Delete Location')
    
    def test_location_create_post(self):
        """Test creating a location via POST request"""
        location_count = Location.objects.count()
        response = self.client.post(
            reverse('sensors:location_create', kwargs={'place_slug': self.place.slug}),
            {
                'name': 'New Test Location',
                'place': self.place.id,
                'is_active': True
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        self.assertEqual(Location.objects.count(), location_count + 1)
        new_location = Location.objects.latest('id')
        self.assertEqual(new_location.name, 'New Test Location')
        self.assertEqual(new_location.place, self.place)  # Verify location belongs to correct place
    
    def test_location_update_post(self):
        """Test updating a location via POST request"""
        response = self.client.post(
            reverse('sensors:location_update', kwargs={
                'place_slug': self.place.slug,
                'pk': self.location.pk
            }),
            {
                'name': 'Updated Location Name',
                'place': self.place.id,
                'is_active': self.location.is_active
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, 'Updated Location Name')
    
    # Device View Tests
    def test_device_list_view(self):
        """Test DeviceListView displays correctly"""
        response = self.client.get(
            reverse('sensors:device_list', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/device_list.html')
        self.assertContains(response, self.device.name)
    
    def test_device_detail_view(self):
        """Test DeviceDetailView displays correctly"""
        response = self.client.get(
            reverse('sensors:device_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.device.pk
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/device_detail.html')
        self.assertContains(response, self.device.name)
    
    def test_device_create_view(self):
        """Test DeviceCreateView displays correctly"""
        response = self.client.get(
            reverse('sensors:device_create', kwargs={
                'place_slug': self.place.slug,
                'location_pk': self.location.pk
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/device_form.html')
        self.assertContains(response, 'Create New Device')
    
    def test_device_update_view(self):
        """Test DeviceUpdateView displays correctly"""
        response = self.client.get(
            reverse('sensors:device_update', kwargs={
                'place_slug': self.place.slug,
                'pk': self.device.pk
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/device_form.html')
        self.assertContains(response, 'Update Device')
    
    def test_device_delete_view(self):
        """Test DeviceDeleteView displays correctly"""
        response = self.client.get(
            reverse('sensors:device_delete', kwargs={
                'place_slug': self.place.slug,
                'pk': self.device.pk
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/device_confirm_delete.html')
        self.assertContains(response, 'Delete Device')
    
    def test_device_create_post(self):
        """Test creating a device via POST request"""
        device_count = Device.objects.count()
        response = self.client.post(
            reverse('sensors:device_create', kwargs={
                'place_slug': self.place.slug,
                'location_pk': self.location.pk
            }),
            {
                'name': 'New Test Device',
                'location': self.location.id,
                'is_active': True,
                'device_type': self.device_type.id,
                'manufacturer': 'Test Manufacturer',
                'model': 'Test Model',
                'serial_number': 'TEST123'
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        self.assertEqual(Device.objects.count(), device_count + 1)
        new_device = Device.objects.latest('id')
        self.assertEqual(new_device.name, 'New Test Device')
        self.assertEqual(new_device.location, self.location)  # Verify device belongs to correct location
    
    # Sensor View Tests
    def test_sensor_list_view(self):
        """Test SensorListView displays correctly"""
        response = self.client.get(
            reverse('sensors:sensor_list', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/sensor_list.html')
        self.assertContains(response, self.sensor.name)
    
    def test_sensor_detail_view(self):
        """Test SensorDetailView displays correctly"""
        response = self.client.get(
            reverse('sensors:sensor_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.sensor.pk
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/sensor_detail.html')
        self.assertContains(response, self.sensor.name)
    
    def test_sensor_create_view(self):
        """Test SensorCreateView displays correctly"""
        response = self.client.get(
            reverse('sensors:sensor_create', kwargs={
                'place_slug': self.place.slug,
                'device_pk': self.device.pk
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/sensor_form.html')
        self.assertContains(response, 'Create New Sensor')
    
    def test_sensor_update_view(self):
        """Test SensorUpdateView displays correctly"""
        response = self.client.get(
            reverse('sensors:sensor_update', kwargs={
                'place_slug': self.place.slug,
                'pk': self.sensor.pk
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/sensor_form.html')
        self.assertContains(response, 'Update Sensor')
    
    def test_sensor_delete_view(self):
        """Test SensorDeleteView displays correctly"""
        response = self.client.get(
            reverse('sensors:sensor_delete', kwargs={
                'place_slug': self.place.slug,
                'pk': self.sensor.pk
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/sensor_confirm_delete.html')
        self.assertContains(response, 'Delete Sensor')
    
    def test_sensor_create_post(self):
        """Test creating a sensor via POST request"""
        sensor_count = Sensor.objects.count()
        response = self.client.post(
            reverse('sensors:sensor_create', kwargs={
                'place_slug': self.place.slug,
                'device_pk': self.device.pk
            }),
            {
                'name': 'New Test Sensor',
                'device': self.device.id,
                'is_active': True,
                'sensor_type': 'TEMP',
                'unit': '°C',
                'data_type': 'DB'
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        self.assertEqual(Sensor.objects.count(), sensor_count + 1)
        new_sensor = Sensor.objects.latest('id')
        self.assertEqual(new_sensor.name, 'New Test Sensor')
        self.assertEqual(new_sensor.device, self.device)  # Verify sensor belongs to correct device
    
    # Test API endpoints
    def test_place_stats_api(self):
        """Test place_stats API endpoint"""
        response = self.client.get(
            reverse('sensors:place_stats', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('stats', data)
    
    def test_toggle_active_api(self):
        """Test toggle_active API endpoint"""
        # Test toggling a place
        initial_status = self.place.is_active
        data = {
            'model_type': 'place',
            'object_id': self.place.id,
            'is_active': not initial_status
        }
        response = self.client.post(
            reverse('sensors:toggle_active', kwargs={'place_slug': self.place.slug}),
            json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.place.refresh_from_db()
        self.assertEqual(self.place.is_active, not initial_status) 