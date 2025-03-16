from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from sensors.forms import PlaceForm, LocationForm, DeviceForm, SensorForm
from sensors.models import Place, Location, Device, Sensor, DeviceType
from decimal import Decimal
import tempfile
from PIL import Image
import io


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
        self.assertEqual(form.cleaned_data['slug'], 'new-test-place')
    
    def test_latitude_validation(self):
        """Test latitude validation"""
        # Test invalid latitude (out of range)
        form_data = {
            'name': 'New Test Place',
            'is_active': True,
            'latitude': 91.0,  # Invalid: > 90
            'longitude': -0.1278
        }
        form = PlaceForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('latitude', form.errors)
    
    def test_longitude_validation(self):
        """Test longitude validation"""
        # Test invalid longitude (out of range)
        form_data = {
            'name': 'New Test Place',
            'is_active': True,
            'latitude': 51.5074,
            'longitude': 181.0  # Invalid: > 180
        }
        form = PlaceForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('longitude', form.errors)
    
    def test_siteplan_image_validation(self):
        """Test siteplan image validation"""
        # Create a valid image
        image = Image.new('RGB', (200, 200), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        valid_image = SimpleUploadedFile(
            'test_image.jpg',
            image_io.read(),
            content_type='image/jpeg'
        )
        
        # Create an invalid image (too small)
        small_image = Image.new('RGB', (100, 100), color='blue')
        small_image_io = io.BytesIO()
        small_image.save(small_image_io, format='JPEG')
        small_image_io.seek(0)
        invalid_image = SimpleUploadedFile(
            'small_image.jpg',
            small_image_io.read(),
            content_type='image/jpeg'
        )
        
        # Test with valid image
        form_data = {
            'name': 'New Test Place',
            'is_active': True,
            'latitude': 51.5074,
            'longitude': -0.1278
        }
        form_files = {
            'siteplan_image': valid_image
        }
        form = PlaceForm(data=form_data, files=form_files)
        self.assertTrue(form.is_valid())
        
        # Test with invalid image
        form_data = {
            'name': 'New Test Place',
            'is_active': True,
            'latitude': 51.5074,
            'longitude': -0.1278
        }
        form_files = {
            'siteplan_image': invalid_image
        }
        form = PlaceForm(data=form_data, files=form_files)
        self.assertFalse(form.is_valid())
        self.assertIn('siteplan_image', form.errors)


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
    
    def test_valid_form(self):
        """Test that form is valid with correct data"""
        form_data = {
            'name': 'New Test Location',
            'place': self.place.id,
            'is_active': True
        }
        # Mock the devices_active attribute that would normally be added by the view
        self.location.devices_active = Device.objects.filter(location=self.location, is_active=True)
        self.location.devices_active_count = self.location.devices_active.count()
        
        form = LocationForm(data=form_data, place=self.place, locations=[self.location], devices_active=self.location.devices_active)
        self.assertTrue(form.is_valid())
    
    def test_inactive_place_constraint(self):
        """Test that location can't be active if place is inactive"""
        # Make the place inactive
        self.place.is_active = False
        self.place.save()
        
        form_data = {
            'name': 'New Test Location',
            'place': self.place.id,
            'is_active': True  # This should be constrained by the inactive place
        }
        
        # Mock the devices_active attribute that would normally be added by the view
        self.location.devices_active = Device.objects.filter(location=self.location, is_active=True)
        self.location.devices_active_count = self.location.devices_active.count()
        
        form = LocationForm(data=form_data, place=self.place, locations=[self.location], devices_active=self.location.devices_active)
        
        # The form should still be valid, but the is_active field should be disabled
        # and the initial value should be False
        self.assertTrue(form.is_valid())
        self.assertFalse(form.fields['is_active'].initial)
        self.assertTrue(form.fields['is_active'].disabled)


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
        
        # Create a device type
        self.device_type = DeviceType.objects.create(
            name='Gateway',
            description='Gateway device type for testing',
            icon='bi-router',
            is_active=True
        )
        
        # Add devices_active_count to locations for the form
        self.location.devices_active_count = 0
        self.inactive_location.devices_active_count = 0
    
    def test_valid_form(self):
        """Test that form is valid with correct data"""
        form_data = {
            'name': 'New Test Device',
            'location': self.location.id,
            'is_active': True,
            'device_type': self.device_type.id,
            'manufacturer': 'Test Manufacturer',
            'model': 'Test Model',
            'serial_number': 'TEST123'
        }
        form = DeviceForm(data=form_data, place=self.place, locations=[self.location, self.inactive_location])
        self.assertTrue(form.is_valid())
    
    def test_inactive_location_constraint(self):
        """Test that device can't be active if location is inactive"""
        form_data = {
            'name': 'New Test Device',
            'location': self.inactive_location.id,
            'is_active': True,  # This should be invalid with inactive location
            'device_type': self.device_type.id,
            'manufacturer': 'Test Manufacturer',
            'model': 'Test Model',
            'serial_number': 'TEST123'
        }
        form = DeviceForm(data=form_data, place=self.place, locations=[self.location, self.inactive_location])
        self.assertFalse(form.is_valid())
        self.assertIn('is_active', form.errors)
    
    def test_serial_number_uniqueness(self):
        """Test that serial number uniqueness is enforced"""
        # Create a device with a serial number
        Device.objects.create(
            name='Existing Device',
            location=self.location,
            is_active=True,
            device_type=self.device_type,
            manufacturer='Test Manufacturer',
            model='Test Model',
            serial_number='EXISTING123'
        )
        
        # Try to create another device with the same serial number
        form_data = {
            'name': 'New Test Device',
            'location': self.location.id,
            'is_active': True,
            'device_type': self.device_type.id,
            'manufacturer': 'Test Manufacturer',
            'model': 'Test Model',
            'serial_number': 'EXISTING123'  # Same serial number
        }
        form = DeviceForm(data=form_data, place=self.place, locations=[self.location, self.inactive_location])
        
        # The form should still be valid because we're only adding a warning, not an error
        # But we should check for warnings
        self.assertTrue(form.is_valid())
        warnings = form.get_warnings()
        self.assertIn('serial_number', warnings)


class SensorFormTest(TestCase):
    """Test the SensorForm validation"""
    
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
            name='Gateway',
            description='Gateway device type for testing',
            icon='bi-router',
            is_active=True
        )
        
        self.device = Device.objects.create(
            name='Test Device',
            location=self.location,
            is_active=True,
            device_type=self.device_type
        )
        self.inactive_device = Device.objects.create(
            name='Inactive Device',
            location=self.location,
            is_active=False,
            device_type=self.device_type
        )
    
    def test_valid_form(self):
        """Test that form is valid with correct data"""
        form_data = {
            'name': 'New Test Sensor',
            'device': self.device.id,
            'is_active': True,
            'sensor_type': 'TEMP',
            'unit': '°C',
            'data_type': 'API'
        }
        form = SensorForm(data=form_data, device=self.device, initial={'device_active': True})
        self.assertTrue(form.is_valid())
    
    def test_inactive_device_constraint(self):
        """Test that sensor can't be active if device is inactive"""
        form_data = {
            'name': 'New Test Sensor',
            'device': self.inactive_device.id,
            'is_active': True,  # This should be constrained by inactive device
            'sensor_type': 'TEMP',
            'unit': '°C',
            'data_type': 'API'
        }
        form = SensorForm(data=form_data, device=self.inactive_device, initial={'device_active': False})
        
        # The form should be valid, but the is_active field should be disabled
        # and the initial value should be False
        self.assertTrue(form.is_valid())
        self.assertFalse(form.fields['is_active'].initial)
        self.assertTrue(form.fields['is_active'].disabled)
    
    def test_influx_fields_required(self):
        """Test that InfluxDB fields are required when data_type is INFLUX"""
        form_data = {
            'name': 'New Test Sensor',
            'device': self.device.id,
            'is_active': True,
            'sensor_type': 'TEMP',
            'unit': '°C',
            'data_type': 'INFLUX',
            # Missing influx_source and influx_measurement
        }
        form = SensorForm(data=form_data, device=self.device, initial={'device_active': True})
        self.assertFalse(form.is_valid())
        self.assertIn('influx_source', form.errors)
        self.assertIn('influx_measurement', form.errors)
        
        # Now add the required fields
        form_data['influx_source'] = 'test_source'
        form_data['influx_measurement'] = 'test_measurement'
        form = SensorForm(data=form_data, device=self.device, initial={'device_active': True})
        self.assertTrue(form.is_valid()) 