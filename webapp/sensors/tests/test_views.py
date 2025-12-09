from django.test import TestCase, Client
import inspect
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from sensors.models import Place, Location, Device, Sensor, DeviceType, SensorType, Unit, InfluxStore
# from django.core.files.uploadedfile import SimpleUploadedFile
import json
import os
from .test_utils import skip_unless_beta
from sensors.views.device_forms import DeviceForm
from sensors.views.location_forms import LocationForm
from sensors.views.sensor_forms import SensorForm
from sensors.views.place_forms import PlaceForm


class SensorsViewTestCase(TestCase):
    # Specify the full path to fixtures
    fixtures = [
        'sensors/tests/fixtures/test_users.json',
        'sensors/tests/fixtures/test_places.json',
        'sensors/tests/fixtures/test_locations.json',
        # 'sensors/tests/fixtures/test_influxstores.json',
        'sensors/tests/fixtures/test_units.json',
        'sensors/tests/fixtures/test_sensor_types.json',
        'sensors/tests/fixtures/test_devicetypes.json',
        'sensors/tests/fixtures/test_devices.json',
        # 'sensors/tests/fixtures/test_sensors.json',
    ]

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='testuser_views', password='testpassword')
        cls.place = Place.objects.create(
            name='Test Place Views',
            slug='test-place-views',
            is_active=True,
            latitude=52.3676,
            longitude=4.9041
        )
        cls.location = Location.objects.create(
            name='Test Location Views',
            place=cls.place,
            is_active=True
        )
        cls.device_type = DeviceType.objects.create(
            name='Gateway Views',
            description='Gateway device type for testing',
            icon='bi-router',
            is_active=True
        )
        cls.device = Device.objects.create(
            name='Test Device Views',
            location=cls.location,
            is_active=True,
            device_type=cls.device_type
        )
        sensor_type, _ = SensorType.objects.get_or_create(name='Temperature Views')
        unit, _ = Unit.objects.get_or_create(name='Celsius Views', symbol='C')
        cls.sensor = Sensor.objects.create(
            name='Test Sensor Views',
            device=cls.device,
            is_active=True,
            sensor_type=sensor_type,
            unit=unit,
            data_store='DIRECT'
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser_views', password='testpassword')

    # Place View Tests
    def test_place_create_view(self):
        """Test PlaceCreateView displays correctly"""
        response = self.client.get(reverse('sensors:place_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/place_form.html')
        self.assertContains(response, 'New Place')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

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
        self.assertEqual(Place.objects.latest('id').name, 'New Test Place')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_place_list_view(self):
        """Test PlaceListView displays correctly"""
        # Ensure self.place is not None
        self.assertIsNotNone(self.place, "Place object should not be None")

        response = self.client.get(reverse('sensors:place_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/place_list.html')
        self.assertContains(response, self.place.name)

    def test_place_detail_view(self):
        """Test PlaceDetailView displays correctly"""
        # Ensure self.place is not None
        self.assertIsNotNone(self.place, "Place object should not be None")

        response = self.client.get(
            reverse('sensors:place_detail', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/place_detail.html')
        self.assertContains(response, self.place.name)

    def test_place_update_view(self):
        """Test PlaceUpdateView displays correctly"""
        # Ensure self.place is not None
        self.assertIsNotNone(self.place, "Place object should not be None")

        response = self.client.get(
            reverse('sensors:place_update', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/place_form.html')
        self.assertContains(response, 'Edit')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_place_update_post(self):
        """Test updating a place via POST request"""
        # Ensure self.place is not None
        self.assertIsNotNone(self.place, "Place object should not be None")

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

    def test_place_delete_view(self):
        """Test PlaceDeleteView displays correctly"""
        response = self.client.get(
            reverse('sensors:place_delete', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/place_confirm_delete.html')
        self.assertContains(response, 'Delete Place')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

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
            {'confirmation_name': temp_place.name}  # Use the correct field name from the form
        )

        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        self.assertEqual(Place.objects.count(), place_count - 1)
        self.assertFalse(Place.objects.filter(pk=temp_place.pk).exists())
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    # Location View Tests
    def test_location_create_view(self):
        """Test LocationCreateView displays correctly"""
        response = self.client.get(
            reverse('sensors:location_create', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/location_form.html')
        self.assertContains(response, 'New Location')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

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
        self.assertTrue(Location.objects.filter(name='New Test Location').exists())
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_location_list_view(self):
        """Test LocationListView displays correctly"""
        response = self.client.get(
            reverse('sensors:location_list', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/location_list.html')
        self.assertContains(response, self.location.name)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_location_detail_view(self):
        """Test LocationDetailView displays correctly"""
        response = self.client.get(
            reverse('sensors:location_detail', kwargs={
                'place_slug': self.place.slug,
                'slug': self.location.slug
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/location_detail.html')
        self.assertContains(response, self.location.name)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_location_update_view(self):
        """Test LocationUpdateView displays correctly"""
        response = self.client.get(
            reverse('sensors:location_update', kwargs={
                'place_slug': self.place.slug,
                'slug': self.location.slug
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/location_form.html')
        self.assertContains(response, 'Edit Location')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_location_update_post(self):
        """Test updating a location via POST request"""
        response = self.client.post(
            reverse('sensors:location_update', kwargs={
                'place_slug': self.place.slug,
                'slug': self.location.slug
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
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_location_delete_view(self):
        """Test LocationDeleteView displays correctly"""
        response = self.client.get(
            reverse('sensors:location_delete', kwargs={
                'place_slug': self.place.slug,
                'slug': self.location.slug
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/location_confirm_delete.html')
        self.assertContains(response, 'Delete Location')

    # Device View Tests
    def test_device_create_view(self):
        """Test DeviceCreateView displays correctly"""
        response = self.client.get(
            reverse('sensors:device_create_in_location', kwargs={
                'place_slug': self.place.slug,
                'location_slug': self.location.slug
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/device_form.html')
        self.assertContains(response, 'New Device')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_device_create_post(self):
        """Test creating a device via POST request"""
        device_count = Device.objects.count()
        response = self.client.post(
            reverse('sensors:device_create_in_location', kwargs={
                'place_slug': self.place.slug,
                'location_slug': self.location.slug
            }),
            {
                'name': 'New Test Device',
                'location': self.location.id,
                'is_active': True,
                'device_type': self.device_type.id,
                'manufacturer': 'Test Manufacturer',
                'model': 'Test Model',
                'device_id': 'TEST123'
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        self.assertEqual(Device.objects.count(), device_count + 1)
        self.assertTrue(Device.objects.filter(name='New Test Device').exists())
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_device_list_view(self):
        """Test DeviceListView displays correctly"""
        response = self.client.get(
            reverse('sensors:device_list', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/device_list.html')
        self.assertContains(response, self.device.name)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

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
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

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
        self.assertContains(response, 'Edit Device')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_device_update_post(self):
        """Test updating a device via POST request"""
        response = self.client.post(
            reverse('sensors:device_update', kwargs={
                'place_slug': self.place.slug,
                'pk': self.device.pk
            }),
            {
                'name': 'Updated Device Name',
                'location': self.location.id,
                'is_active': self.device.is_active
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        self.device.refresh_from_db()
        self.assertEqual(self.device.name, 'Updated Device Name')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_device_delete_view(self):
        """Test DeviceDeleteView displays correctly for both standard and HTMX requests."""
        device = Device.objects.create(name="Device to Delete", location=self.location, device_type=self.device_type)

        # Test standard GET request
        response_std = self.client.get(reverse('sensors:device_delete', kwargs={'place_slug': self.place.slug, 'pk': device.pk}))
        self.assertEqual(response_std.status_code, 200)
        self.assertTemplateUsed(response_std, 'sensors/device_confirm_delete.html')

        # Test HTMX GET request
        response_htmx = self.client.get(reverse('sensors:device_delete', kwargs={'place_slug': self.place.slug, 'pk': device.pk}), HTTP_HX_REQUEST='true')
        self.assertEqual(response_htmx.status_code, 200)
        # Check that the main modal partial is in the list of templates used
        self.assertIn('sensors/partials/device_confirm_delete_modal.html', [t.name for t in response_htmx.templates])

        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_device_delete_post(self):
        """Test DeviceDeleteView handles POST correctly"""
        device = Device.objects.create(name="Device to Delete", location=self.location, device_type=self.device_type)
        device_count_before = Device.objects.count()

        # Simulate a standard form POST (no HTMX header)
        response = self.client.post(
            reverse('sensors:device_delete', kwargs={'place_slug': self.place.slug, 'pk': device.pk}),
            {'confirmation_name': device.name}  # Add confirmation name to make form valid
        )

        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        self.assertEqual(Device.objects.count(), device_count_before - 1)
        with self.assertRaises(Device.DoesNotExist):
            Device.objects.get(pk=device.pk)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    # Sensor View Tests
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
        self.assertContains(response, 'New Sensor')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_sensor_create_post(self):
        """Test creating a sensor via POST request"""
        # Make sure the device is active for this test
        self.device.is_active = True
        self.device.save()

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
                'sensor_type': self.sensor.sensor_type.pk,
                'unit': self.sensor.unit.pk,
                'data_store': 'DIRECT',
                'graph_type': 'LINE',
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        self.assertEqual(Sensor.objects.count(), sensor_count + 1)
        self.assertTrue(Sensor.objects.filter(name='New Test Sensor').exists())
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_sensor_list_view(self):
        """Test SensorListView displays correctly"""
        response = self.client.get(
            reverse('sensors:sensor_list', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/sensor_list.html')
        self.assertContains(response, self.sensor.name)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

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
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

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
        self.assertContains(response, 'Edit Sensor')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_sensor_update_post(self):
        """Test updating a sensor via POST request"""
        response = self.client.post(
            reverse('sensors:sensor_update', kwargs={
                'place_slug': self.place.slug,
                'pk': self.sensor.pk
            }),
            {
                'name': 'Updated Sensor Name',
                'is_active': self.sensor.is_active,
                'device': self.sensor.device.pk,
                'sensor_type': self.sensor.sensor_type.pk,
                'unit': self.sensor.unit.pk,
                'data_store': self.sensor.data_store,
                'graph_type': self.sensor.graph_type or '',
                'description': 'An updated test sensor.'
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        self.sensor.refresh_from_db()
        self.assertEqual(self.sensor.name, 'Updated Sensor Name')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    # Test API endpoints
    def test_place_stats_api(self):
        """Test place_stats API endpoint"""
        response = self.client.get(
            reverse('sensors:place_stats_api', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('stats', data)
        self.assertIn('locations_active', data['stats'])
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_toggle_active_api(self):
        """Test toggle_active API endpoint"""
        # Test toggling the device
        initial_status = self.device.is_active
        data = {
            'model_type': 'device',
            'id': self.device.pk,
            'is_active': not initial_status
        }
        response = self.client.post(
            reverse('sensors:toggle_active', kwargs={'place_slug': self.place.slug}),
            json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Refresh from database to get updated status
        self.device.refresh_from_db()
        self.assertEqual(self.device.is_active, not initial_status)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")
