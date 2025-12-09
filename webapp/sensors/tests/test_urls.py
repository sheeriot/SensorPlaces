from django.test import TestCase, Client
import inspect
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model
from sensors.models import Place, Location, Device, Sensor, DeviceType, SensorType, Unit
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
from .test_utils import skip_unless_beta


class URLResolveTestCase(TestCase):
    """Test that URLs resolve to the correct view functions/classes"""

    def test_place_urls_resolve(self):
        """Test place URLs resolve to correct views"""
        self.assertEqual(resolve(reverse('sensors:place_list')).func.view_class, PlaceListView)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_location_urls_resolve(self):
        """Test location URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:location_list', kwargs={'place_slug': 'test-place'})).func.view_class,
            LocationListView
        )
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_device_urls_resolve(self):
        """Test device URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:device_list', kwargs={'place_slug': 'test-place'})).func.view_class,
            DeviceListView
        )
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_sensor_urls_resolve(self):
        """Test sensor URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:sensor_list', kwargs={'place_slug': 'test-place'})).func.view_class,
            SensorListView
        )
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_api_urls_resolve(self):
        """Test API URLs resolve to correct views"""
        self.assertEqual(
            resolve(reverse('sensors:toast_api', kwargs={'place_slug': 'test-place'})).func.view_class,
            ToastAPIView
        )
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")


class URLAccessTestCase(TestCase):
    """Test access to URLs with authentication and permissions"""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='testuser_urls', password='testpassword')
        cls.place = Place.objects.create(
            name='Test Place URLs',
            slug='test-place-urls',
            is_active=True,
            latitude=52.3676,
            longitude=4.9041
        )
        cls.location = Location.objects.create(
            name='Test Location URLs',
            place=cls.place,
            is_active=True
        )
        cls.device_type = DeviceType.objects.create(
            name='Gateway URLs',
            description='Gateway device type for testing',
            icon='bi-router',
            is_active=True
        )
        cls.device = Device.objects.create(
            name='Test Device URLs',
            location=cls.location,
            is_active=True,
            device_type=cls.device_type
        )
        sensor_type, _ = SensorType.objects.get_or_create(name='Temperature URLs')
        unit, _ = Unit.objects.get_or_create(name='Celsius URLs', symbol='C')
        cls.sensor = Sensor.objects.create(
            name='Test Sensor URLs',
            device=cls.device,
            is_active=True,
            sensor_type=sensor_type,
            unit=unit,
            data_store='DIRECT'
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser_urls', password='testpassword')

    # Place URL Access Tests
    def test_place_create_access(self):
        """Test access to place create view"""
        self.assertEqual(self.client.get(reverse('sensors:place_create')).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_place_list_access(self):
        """Test access to place list view"""
        self.assertEqual(self.client.get(reverse('sensors:place_list')).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_place_detail_access(self):
        """Test access to place detail view"""
        self.assertEqual(self.client.get(
            reverse('sensors:place_detail', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_place_update_access(self):
        """Test access to place update view"""
        self.assertEqual(self.client.get(
            reverse('sensors:place_update', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    # Location URL Access Tests
    def test_location_create_access(self):
        """Test access to location create view"""
        self.assertEqual(self.client.get(
            reverse('sensors:location_create', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_location_list_access(self):
        """Test access to location list view"""
        self.assertEqual(self.client.get(
            reverse('sensors:location_list', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_location_detail_access(self):
        """Test access to location detail view"""
        self.assertEqual(self.client.get(
            reverse('sensors:location_detail', kwargs={
                'place_slug': self.place.slug,
                'slug': self.location.slug
            })
        ).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    # Device URL Access Tests
    def test_device_create_access(self):
        """Test access to device create view"""
        self.assertEqual(self.client.get(
            reverse('sensors:device_create', kwargs={
                'place_slug': self.place.slug
            })
        ).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_device_list_access(self):
        """Test access to device list view"""
        self.assertEqual(self.client.get(
            reverse('sensors:device_list', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_device_detail_access(self):
        """Test access to device detail view"""
        self.assertEqual(self.client.get(
            reverse('sensors:device_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.device.pk
            })
        ).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    # Sensor URL Access Tests
    def test_sensor_create_access(self):
        """Test access to sensor create view"""
        self.assertEqual(self.client.get(
            reverse('sensors:sensor_create', kwargs={
                'place_slug': self.place.slug,
                'device_pk': self.device.pk
            })
        ).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_sensor_list_access(self):
        """Test access to sensor list view"""
        self.assertEqual(self.client.get(
            reverse('sensors:sensor_list', kwargs={'place_slug': self.place.slug})
        ).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    def test_sensor_detail_access(self):
        """Test access to sensor detail view"""
        self.assertEqual(self.client.get(
            reverse('sensors:sensor_detail', kwargs={
                'place_slug': self.place.slug,
                'pk': self.sensor.pk
            })
        ).status_code, 200)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    # API URL Access Tests
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
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")


class FormSubmissionTestCase(TestCase):
    """Test form submissions through views"""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='testuser_forms', password='testpassword')
        cls.place = Place.objects.create(
            name='Test Place Forms',
            slug='test-place-forms',
            is_active=True,
            latitude=52.3676,
            longitude=4.9041
        )
        cls.location = Location.objects.create(
            name='Test Location Forms',
            place=cls.place,
            is_active=True
        )
        cls.device_type = DeviceType.objects.create(
            name='Gateway Forms',
            description='Gateway device type for testing',
            icon='bi-router',
            is_active=True
        )
        cls.device = Device.objects.create(
            name='Test Device Forms',
            location=cls.location,
            is_active=True,
            device_type=cls.device_type
        )
        sensor_type, _ = SensorType.objects.get_or_create(name='Temperature Forms')
        unit, _ = Unit.objects.get_or_create(name='Celsius Forms', symbol='C')
        cls.sensor = Sensor.objects.create(
            name='Test Sensor Forms',
            device=cls.device,
            is_active=True,
            sensor_type=sensor_type,
            unit=unit,
            data_store='DIRECT'
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser_forms', password='testpassword')

    # Place Form Submission Tests
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
            method = getattr(self, self._testMethodName)
            _, start_line = inspect.getsourcelines(method)
            print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")
        except Exception as e:
            print(f"==>> {self.__class__.__name__}: test_place_create_form FAIL: {str(e)}")
            raise

    # Location Form Submission Tests
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
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    # Device Form Submission Tests
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
            'device_id': 'TEST123'
        }
        self.assertEqual(self.client.post(
            reverse('sensors:device_create', kwargs={
                'place_slug': self.place.slug
            }),
            form_data
        ).status_code, 302)
        self.assertEqual(Device.objects.count(), device_count + 1)
        self.assertEqual(Device.objects.latest('id').name, 'New Test Device')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    # Sensor Form Submission Tests
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
            'sensor_type': self.sensor.sensor_type.pk,
            'unit': self.sensor.unit.pk,
            'data_store': 'DIRECT',
            'graph_type': 'LINE',
            'influx_measurement': 'test_measurement',
            'referrer': '',
        }

        url = reverse('sensors:sensor_create', kwargs={
            'place_slug': self.place.slug,
            'device_pk': self.device.pk
        })

        response = self.client.post(url, form_data)
        if response.status_code != 302:
            print(response.context['form'].errors)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sensor.objects.count(), sensor_count + 1)
        self.assertEqual(Sensor.objects.latest('id').name, 'New Test Sensor')
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

    # API Form Submission Tests
    def test_toggle_active_api(self):
        """Test toggling active status via API for a device with dependent sensors"""
        # Get CSRF token
        response = self.client.get(reverse('sensors:place_detail', kwargs={'place_slug': self.place.slug}))
        csrf_token = self.client.cookies.get('csrftoken')
        csrf_value = csrf_token.value if csrf_token else ''

        # Test deactivating the device
        data = {
            'model_type': 'device',
            'id': self.device.pk,
            'is_active': False,
            'csrf_token': csrf_value
        }

        response = self.client.post(
            reverse('sensors:toggle_active', kwargs={'place_slug': self.place.slug}),
            json.dumps(data),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_value
        )

        # Check the response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertFalse(response_data['new_state'])
        self.assertEqual(response_data['dependencies'][0]['name'], self.sensor.name)
        method = getattr(self, self._testMethodName)
        _, start_line = inspect.getsourcelines(method)
        print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")
