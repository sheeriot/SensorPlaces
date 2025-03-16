from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from sensors.models import Place, Location, Device, Sensor, SensorReading
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
        'sensors/tests/fixtures/test_readings.json',
    ]

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        self.place = Place.objects.get(slug='5702hb')

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

    def test_location_list_view(self):
        """Test LocationListView displays correctly"""
        response = self.client.get(
            reverse('sensors:location_list', kwargs={'place_slug': self.place.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sensors/location_list.html')

    # Add more test methods for each view... 