from django.test import TestCase
from sensors.views.place_forms import PlaceForm, PlaceDeleteForm
from sensors.views.location_forms import LocationForm
from sensors.views.device_forms import DeviceForm
from sensors.views.sensor_forms import SensorForm
from sensors.models import Place, Location, Device, Sensor, DeviceType, InfluxSource
from django.test import Client
from django.urls import reverse
import json
from django.contrib.auth import get_user_model
import datetime
import random
from django.db.models import Count, Q
from django.db.models.functions import Lower


class PlaceFormTest(TestCase):
    """Test the PlaceForm validation"""
    
    def setUp(self):
        self.place = Place.objects.create(
            name='Test Place',
            slug='test-place',
            is_active=True,
            latitude=52.3676,
            longitude=4.9041
        )
    
    def test_valid_form(self):
        """Test that form is valid with correct data"""
        form_data = {
            'name': 'New Test Place',
            'is_active': True,
            'latitude': 51.5074,
            'longitude': -0.1278
        }
        form = PlaceForm(data=form_data)
        self.assertTrue(form.is_valid())
        print("===> test_forms.py --> test_valid_form PASS")
    
    def test_slug_generation(self):
        """Test that slug is generated correctly"""
        form_data = {
            'name': 'New Test Place',
            'is_active': True,
            'latitude': 51.5074,
            'longitude': -0.1278
        }
        form = PlaceForm(data=form_data)
        self.assertTrue(form.is_valid())
        place = form.save()
        self.assertEqual(place.slug, 'new-test-place')
        print("===> test_forms.py --> test_slug_generation PASS")
    
    def test_latitude_validation(self):
        """Test that latitude is validated correctly"""
        # Test with latitude too high
        form_data = {
            'name': 'Invalid Latitude Place',
            'is_active': True,
            'latitude': 91.0,  # Invalid: above 90
            'longitude': 0.0
        }
        form = PlaceForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('latitude', form.errors)
        print("===> test_forms.py --> test_latitude_validation PASS")
    
    def test_longitude_validation(self):
        """Test that longitude is validated correctly"""
        # Test with longitude too low
        form_data = {
            'name': 'Invalid Longitude Place',
            'is_active': True,
            'latitude': 0.0,
            'longitude': -181.0  # Invalid: below -180
        }
        form = PlaceForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('longitude', form.errors)
        print("===> test_forms.py --> test_longitude_validation PASS")
    
    def test_siteplan_image_validation(self):
        """Test that siteplan image is validated correctly"""
        # Create a valid form without image
        form_data = {
            'name': 'Place Without Image',
            'is_active': True,
            'latitude': 51.5074,
            'longitude': -0.1278,
        }
        
        # Test with no image (should be valid)
        form = PlaceForm(data=form_data)
        self.assertTrue(form.is_valid())
        print("===> test_forms.py --> test_siteplan_image_validation PASS")


class LocationFormTest(TestCase):
    """Test the LocationForm validation"""
    
    def setUp(self):
        self.place = Place.objects.create(
            name='Test Place',
            slug='test-place',
            is_active=True,
            latitude=52.3676,
            longitude=4.9041
        )
        self.location = Location.objects.create(
            name='Test Location',
            place=self.place,
            is_active=True
        )
        
        # Create a device type
        self.device_type = DeviceType.objects.create(
            name='Test Device Type',
            description='Test device type for testing',
            icon='bi-hdd',
            is_active=True
        )
        
        self.device = Device.objects.create(
            name='Test Device',
            location=self.location,
            is_active=True,
            device_type=self.device_type
        )
    
    def get_devices_active(self):
        """Get active devices for the location as the view would."""
        return Device.objects.filter(location=self.location, is_active=True).annotate(
            sensor_count=Count(
                'sensors',
                filter=Q(sensors__is_active=True))
        ).prefetch_related('sensors')
    
    def test_valid_form(self):
        """Test that form is valid with correct data"""
        place = Place.objects.create(
            name='New Place',
            slug='new-place',
            is_active=True,
            latitude=52.3676,
            longitude=4.9041
        )
        
        form_data = {
            'name': 'New Test Location',
            'place': place.pk,
            'is_active': True
        }
        form = LocationForm(data=form_data, place=place)
        self.assertTrue(form.is_valid())
        print("===> test_forms.py --> test_valid_form (LocationFormTest) PASS")
    
    def test_inactive_place_constraint(self):
        """Test that a location's is_active is automatically set to False if its place is inactive"""
        # Create an inactive place
        place = Place.objects.create(
            name='Inactive Place',
            slug='inactive-place',
            is_active=False,
            latitude=52.3676,
            longitude=4.9041
        )
        
        # Form data with is_active=False is valid with inactive place
        form_data = {
            'name': 'New Test Location',
            'place': place.pk,
            'is_active': False
        }
        # Pass the place directly to the form
        form = LocationForm(data=form_data, place=place)
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data['is_active'])
        
        # Set the instance to make is_active field disabled
        location = Location(place=place, is_active=False)
        form = LocationForm(data=form_data, instance=location, place=place)
        
        # Check that is_active gets disabled when the place is inactive
        self.assertIn('is_active', form.fields)
        self.assertTrue(form.fields['is_active'].widget.attrs.get('disabled', False))
        
        # Form data with is_active=True is invalid with inactive place
        form_data = {
            'name': 'New Test Location',
            'place': place.pk,
            'is_active': True
        }
        
        form = LocationForm(data=form_data, place=place)
        self.assertFalse(form.is_valid())
        self.assertIn('is_active', form.errors)
        # Check that the right error message is raised
        self.assertIn('Location cannot be active', str(form.errors['is_active']))
        print("===> test_forms.py --> test_inactive_place_constraint PASS")


class DeviceFormTest(TestCase):
    """Test the DeviceForm validation"""
    
    def setUp(self):
        self.place = Place.objects.create(
            name='Test Place',
            slug='test-place',
            is_active=True,
            latitude=52.3676,
            longitude=4.9041
        )
        self.location = Location.objects.create(
            name='Test Location',
            place=self.place,
            is_active=True
        )
        self.inactive_location = Location.objects.create(
            name='Inactive Location',
            place=self.place,
            is_active=False
        )
        
        # Create a device type with a unique name using timestamp
        unique_suffix = f"{datetime.datetime.now().timestamp()}-{random.randint(1000, 9999)}"
        self.device_type = DeviceType.objects.create(
            name=f'Gateway-{unique_suffix}',
            description='Gateway device type for testing',
            icon='bi-router',
            is_active=True
        )
    
    def get_annotated_locations(self):
        """Get locations with the same annotations as PlaceAnnotationMixin."""
        return Location.objects.filter(place=self.place).annotate(
            devices_active_count=Count(
                'devices',
                filter=Q(devices__is_active=True),
                distinct=True
            ),
            devices_inactive_count=Count(
                'devices',
                filter=Q(devices__is_active=False),
                distinct=True
            ),
            sensors_active_count=Count(
                'devices__sensors',
                filter=Q(devices__sensors__is_active=True),
                distinct=True
            ),
            sensors_inactive_count=Count(
                'devices__sensors',
                filter=Q(devices__sensors__is_active=False),
                distinct=True
            )
        ).order_by('-is_active', Lower('name'))
    
    def test_valid_form(self):
        """Test that form is valid with correct data"""
        form_data = {
            'name': 'New Test Device',
            'location': self.location.pk,
            'is_active': True,
            'device_type': self.device_type.pk,
            'model': 'Test Model',
            'manufacturer': 'Test Manufacturer',
            'device_id': 'TEST123'
        }
        
        form = DeviceForm(data=form_data)
        self.assertTrue(form.is_valid())
        print("===> test_forms.py --> test_valid_form (DeviceFormTest) PASS")
    
    def test_inactive_location_constraint(self):
        """Test that device can't be active if location is inactive"""
        # Make the location inactive
        self.location.is_active = False
        self.location.save()
        
        form_data = {
            'name': 'New Test Device',
            'location': self.location.pk,
            'is_active': False,  # Set this to False to make the form valid
            'device_type': self.device_type.pk,
            'model': 'Test Model',
            'manufacturer': 'Test Manufacturer',
            'device_id': 'TEST456'
        }
        
        form = DeviceForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data['is_active'])
        
        # Form is invalid if is_active=True with inactive location
        form_data['is_active'] = True
        form = DeviceForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('is_active', form.errors)
        print("===> test_forms.py --> test_inactive_location_constraint PASS")
        
    def test_device_form_uniqueness(self):
        """Test device form uniqueness validation"""
        # Create an initial device
        Device.objects.create(
            name='Existing Device',
            location=self.location,
            device_type=self.device_type,
            device_id='EXISTING123'
        )

        # Form with a new, unique device_id should be valid
        form_new = DeviceForm(data={
            'name': 'New Device',
            'location': self.location.pk,
            'device_type': self.device_type.pk,
            'device_id': 'DIFFERENT123'
        })
        self.assertTrue(form_new.is_valid())

        # Form with a duplicate device_id should have warnings
        form_duplicate = DeviceForm(data={
            'name': 'Another Device',
            'location': self.location.pk,
            'device_type': self.device_type.pk,
            'device_id': 'EXISTING123'
        })
        self.assertTrue(form_duplicate.is_valid())  # is_valid should be true
        warnings = form_duplicate.get_warnings()
        self.assertIn('device_id', warnings)
        self.assertIn('already exists', warnings['device_id'][0])
        print("===> test_forms.py --> test_device_form_uniqueness PASS")

    def test_device_form_update_toast(self):
        """Test that updating a device and changing its name creates a toast notification"""
        # First create a device
        device = Device.objects.create(
            name='Original Name',
            location=self.location,
            device_type=self.device_type,
            device_id='TOASTUPDATE123'
        )

        # Form data to update the device
        response = self.client.post(
            reverse('sensors:device_update', kwargs={
                'place_slug': self.place.slug,
                'pk': device.pk
            }),
            {
                'name': 'Updated Toast Device',
                'location': self.location.pk,
                'is_active': True,
                'device_type': self.device_type.pk,
                'manufacturer': 'Updated Manufacturer',
                'model': 'Updated Toast Model',
                'device_id': 'TOASTUPDATE123'
            }
        )
        # Check response is a redirect (indicating success)
        self.assertEqual(response.status_code, 302)
        
        # Check the session for pending_toast
        self.assertIn('pending_toast', self.client.session)
        self.assertIn('message', self.client.session['pending_toast'])
        self.assertIn('Updated Toast Device', self.client.session['pending_toast']['message'])
        self.assertIn('name: Original Name', self.client.session['pending_toast']['message'])
        print("===> test_forms.py --> test_device_form_update_toast PASS")


class SensorFormTest(TestCase):
    """Test the SensorForm validation"""
    
    def setUp(self):
        # Create a place
        self.place = Place.objects.create(
            name='Test Place',
            slug='test-place',
            is_active=True,
            latitude=52.3676,
            longitude=4.9041
        )
        
        # Create a location
        self.location = Location.objects.create(
            name='Test Location',
            place=self.place,
            is_active=True
        )
        
        # Create a device type
        self.device_type = DeviceType.objects.create(
            name='Test Device Type',
            description='Test device type for testing',
            icon='bi-hdd',
            is_active=True
        )
        
        # Create a device
        self.device = Device.objects.create(
            name='Test Device',
            location=self.location,
            is_active=True,
            device_type=self.device_type
        )
        
        # Create an influx source
        self.influx_source = InfluxSource.objects.create(
            name='Test Influx',
            server_dns='localhost',
            server_port=8086,
            bucket_name='test_bucket',
            org='test_org',
            read_token='test_token'
        )
    
    def test_valid_form(self):
        """Test that form is valid with correct data"""
        form_data = {
            'name': 'New Test Sensor',
            'device': self.device.pk,
            'is_active': True,
            'sensor_type': 'TEMP',
            'unit': '°C',
            'data_type': 'DB'
        }
        form = SensorForm(data=form_data, device=self.device)
        self.assertTrue(form.is_valid())
        print("===> test_forms.py --> test_valid_form (SensorFormTest) PASS")
    
    def test_inactive_device_constraint(self):
        """Test that a sensor's is_active is automatically set to False if its device is inactive"""
        # Make the device inactive
        self.device.is_active = False
        self.device.save()
        
        # Form data with is_active=False is valid with inactive device
        form_data = {
            'name': 'New Test Sensor',
            'device': self.device.pk,
            'is_active': False,
            'sensor_type': 'TEMP',
            'unit': '°C',
            'data_type': 'DB'
        }
        
        form = SensorForm(data=form_data, device=self.device)
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data['is_active'])
        
        # Form data with is_active=True is invalid with inactive device
        form_data = {
            'name': 'New Test Sensor',
            'device': self.device.pk,
            'is_active': True,
            'sensor_type': 'TEMP',
            'unit': '°C',
            'data_type': 'DB'
        }
        
        form = SensorForm(data=form_data, device=self.device)
        self.assertFalse(form.is_valid())
        self.assertIn('is_active', form.errors)
        # Check that the right error message is raised
        self.assertIn('Sensor cannot be active', str(form.errors['is_active']))
        print("===> test_forms.py --> test_inactive_device_constraint PASS")
    
    def test_influx_fields_required(self):
        """Test that InfluxDB fields are required when data_type is INFLUX"""
        # Form with data_type=INFLUX but missing influx_source and influx_measurement should be invalid
        form_data = {
            'name': 'New Test Sensor',
            'device': self.device.pk,
            'is_active': True,
            'sensor_type': 'TEMP',
            'unit': '°C',
            'data_type': 'INFLUX'
        }
        
        form = SensorForm(data=form_data, device=self.device)
        self.assertFalse(form.is_valid())
        self.assertIn('influx_source', form.errors)
        self.assertIn('influx_measurement', form.errors)
        
        # Form with data_type=INFLUX and all required fields should be valid
        form_data = {
            'name': 'New Test Sensor',
            'device': self.device.pk,
            'is_active': True,
            'sensor_type': 'TEMP',
            'unit': '°C',
            'data_type': 'INFLUX',
            'influx_source': self.influx_source.pk,
            'influx_measurement': 'test_measurement'
        }
        
        form = SensorForm(data=form_data, device=self.device)
        self.assertTrue(form.is_valid())
        print("===> test_forms.py --> test_influx_fields_required PASS")
        
    def test_form_html_rendering(self):
        """Test that the SensorForm correctly generates HTML with form tags"""
        form = SensorForm(device=self.device)
        
        # Check form helper configuration
        self.assertTrue(form.helper.form_tag)
        self.assertEqual(form.helper.form_method, 'post')
        
        # Verify that key fields are in the form layout
        layout_fields = self._get_layout_field_names(form.helper.layout)
        self.assertIn('name', layout_fields)
        self.assertIn('device', layout_fields)
        self.assertIn('is_active', layout_fields)
        self.assertIn('sensor_type', layout_fields)
        self.assertIn('unit', layout_fields)
        self.assertIn('data_type', layout_fields)
        
        # Check if the submit button is included
        has_submit = self._layout_has_submit(form.helper.layout)
        self.assertTrue(has_submit, "Form should include a submit button")
        
        print("===> test_forms.py --> test_form_html_rendering PASS")
    
    def _get_layout_field_names(self, layout):
        """Extract field names from a layout object recursively"""
        field_names = []
        
        if hasattr(layout, 'fields'):
            for field in layout.fields:
                if hasattr(field, 'fields'):
                    field_names.extend(self._get_layout_field_names(field))
                elif hasattr(field, 'field'):
                    field_names.append(field.field)
                elif isinstance(field, str):
                    field_names.append(field)
        
        return field_names
    
    def _layout_has_submit(self, layout):
        """Check if layout contains a submit button"""
        if hasattr(layout, 'fields'):
            for field in layout.fields:
                if hasattr(field, 'fields'):
                    if self._layout_has_submit(field):
                        return True
                elif str(field).lower().find('submit') >= 0:
                    return True
                elif hasattr(field, 'content'):
                    content = str(field.content).lower()
                    if 'submit' in content or 'type="submit"' in content:
                        return True
        return False


class ToastMessageTestCase(TestCase):
    """Test that toast messages are correctly generated for form submissions"""
    
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='toastuser',
            email='toast@example.com',
            password='toastpass123'
        )
        self.client.login(username='toastuser', password='toastpass123')
        
        # Create test data
        self.place = Place.objects.create(
            name='Toast Place',
            slug='toast-place',
            is_active=True,
            latitude=52.3676,
            longitude=4.9041
        )
            
        self.location = Location.objects.create(
            name='Toast Location',
            place=self.place,
            is_active=True
        )
            
        # Create a device type
        self.device_type = DeviceType.objects.create(
            name='Toast Device Type',
            description='Device type for toast testing',
            icon='bi-router',
            is_active=True
        )
            
        self.device = Device.objects.create(
            name='Toast Device',
            location=self.location,
            is_active=True,
            device_type=self.device_type
        )
    
    def test_create_toast_messages(self):
        """Test that creating a place, location, device, and sensor generates toast messages"""
        # Create a place
        response = self.client.post(
            reverse('sensors:place_create'),
            {
                'name': 'New Toast Place',
                'is_active': True,
                'latitude': 51.5074,
                'longitude': -0.1278
            }
        )
        # Check response is a redirect (indicating success)
        self.assertEqual(response.status_code, 302)
        # Check the session for pending_toast
        self.assertIn('pending_toast', self.client.session)
        self.assertIn('message', self.client.session['pending_toast'])
        self.assertIn('New Toast Place', self.client.session['pending_toast']['message'])
        
        # Clear session to prepare for next test
        session = self.client.session
        if 'pending_toast' in session:
            del session['pending_toast']
            session.save()
        print("===> test_forms.py --> test_create_toast_messages PASS")
    
    def test_update_device_toast_messages(self):
        """Test that updating a device generates correct toast messages with changed fields"""
        # First create a device
        device = Device.objects.create(
            name='catnip',
            location=self.location,
            is_active=False,
            device_type=self.device_type,
            manufacturer='Mouse',
            model='woolen',
            device_id='yy'
        )
        
        # Now update it with changes to all fields
        response = self.client.post(
            reverse('sensors:device_update', kwargs={
                'place_slug': self.place.slug,
                'pk': device.pk
            }),
            {
                'name': 'Updated Toast Device',
                'location': self.location.pk,
                'is_active': True,
                'device_type': self.device_type.pk,
                'manufacturer': 'Updated Manufacturer',
                'model': 'Updated Toast Model',
                'device_id': 'TOASTUPDATE123'
            }
        )
        # Check response is a redirect (indicating success)
        self.assertEqual(response.status_code, 302)
        
        # Check the session for pending_toast
        self.assertIn('pending_toast', self.client.session)
        self.assertIn('message', self.client.session['pending_toast'])
        self.assertIn('Updated Toast Device', self.client.session['pending_toast']['message'])
        self.assertIn('name: catnip', self.client.session['pending_toast']['message'])
        print("===> test_forms.py --> test_update_device_toast_messages PASS")
    
    def test_toggle_active_toast_messages(self):
        """Test that toggling active status generates correct toast messages"""
        # Ensure the device is active first
        self.device.is_active = True
        self.device.save()
        
        # Set up CSRF token
        response = self.client.get(reverse('sensors:place_detail', kwargs={'place_slug': self.place.slug}))
        csrf_token = response.cookies.get('csrftoken', None)
        if csrf_token:
            csrf_token = csrf_token.value
        else:
            csrf_token = 'test-csrf-token'  # Fallback for testing
        
        # Toggle the device inactive - should deactivate dependent sensors too
        response = self.client.post(
            reverse('sensors:toggle_active', kwargs={'place_slug': self.place.slug}),
            json.dumps({
                'model_type': 'device',
                'id': self.device.pk,
                'is_active': False
            }),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Check the actual active state in the response
        if 'is_active' in response_data:
            self.assertFalse(response_data['is_active'])
        
        # Verify toast message in JSON response
        toast_key = 'toast_data' if 'toast_data' in response_data else 'toast'
        self.assertTrue(toast_key in response_data)
        self.assertIn('message', response_data[toast_key])
        print("===> test_forms.py --> test_toggle_active_toast_messages PASS")

    def test_place_delete_form_validation(self):
        """Test that PlaceDeleteForm requires the correct name confirmation"""
        # Create a test place
        test_place = Place.objects.create(
            name='Delete Test Place',
            slug='delete-test-place',
            is_active=True,
            latitude=53.4808,
            longitude=-2.2426
        )
        
        # Test with incorrect name
        form_data = {
            'confirmation_name': 'Wrong Name'
        }
        form = PlaceDeleteForm(data=form_data, instance=test_place)
        self.assertFalse(form.is_valid())
        self.assertIn('confirmation_name', form.errors)
        
        # Test with correct name
        form_data = {
            'confirmation_name': 'Delete Test Place'
        }
        form = PlaceDeleteForm(data=form_data, instance=test_place)
        self.assertTrue(form.is_valid())
        print("===> test_forms.py --> test_place_delete_form_validation PASS") 