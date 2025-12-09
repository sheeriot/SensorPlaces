from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from sensors.models import Place, Location, Device, Sensor
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import json
import unittest


class JavaScriptInteractionTestCase(unittest.TestCase):
    """
    Test JavaScript interactions using Selenium.

    Note: These tests require Selenium and a compatible webdriver.
    To run these tests, you'll need to:
    1. Install Selenium: pip install selenium
    2. Download the appropriate webdriver (Chrome, Firefox, etc.)
    3. Make sure the webdriver is in your PATH

    These tests are marked with @unittest.skip by default since they require
    a browser and are slower than regular tests. Remove the skip decorator
    to run them.
    """

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests"""
        # Skip setup if tests are being skipped
        if getattr(cls, '__unittest_skip__', False):
            return

        # Set up Chrome options for headless testing
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        # Initialize the WebDriver
        try:
            cls.driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"Could not initialize WebDriver: {e}")
            cls.__unittest_skip__ = True
            cls.__unittest_skip_why__ = f"WebDriver initialization failed: {e}"
            return

        # Set up Django test client
        cls.client = Client()

        # Create a test user
        User = get_user_model()
        cls.username = 'testuser'
        cls.password = 'testpass123'
        cls.user = User.objects.create_user(
            username=cls.username,
            email='test@example.com',
            password=cls.password
        )

        # Create test data
        cls.place = Place.objects.create(
            name='Test Place',
            slug='test-place',
            is_active=True,
            latitude=52.3676,
            longitude=4.9041
        )

        cls.location = Location.objects.create(
            name='Test Location',
            place=cls.place,
            is_active=True
        )

        cls.device = Device.objects.create(
            name='Test Device',
            location=cls.location,
            is_active=True,
            device_type='GATEWAY'
        )

        cls.sensor = Sensor.objects.create(
            name='Test Sensor',
            device=cls.device,
            is_active=True,
            sensor_type='TEMP',
            unit='°C',
            data_store='API'
        )

        # Set up the base URL
        cls.live_server_url = 'http://localhost:8000'  # Adjust as needed

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        # Skip teardown if tests are being skipped
        if getattr(cls, '__unittest_skip__', False):
            return

        # Close the browser
        if hasattr(cls, 'driver'):
            cls.driver.quit()

    def setUp(self):
        """Set up before each test"""
        # Skip if tests are being skipped
        if getattr(self.__class__, '__unittest_skip__', False):
            self.skipTest(self.__class__.__unittest_skip_why__)

        # Log in the user
        self.driver.get(f"{self.live_server_url}/accounts/login/")
        username_input = self.driver.find_element(By.NAME, "login")
        password_input = self.driver.find_element(By.NAME, "password")
        username_input.send_keys(self.username)
        password_input.send_keys(self.password)
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Wait for login to complete
        WebDriverWait(self.driver, 10).until(
            EC.url_contains("/")
        )

    @unittest.skip("Requires browser and server running")
    def test_toggle_place_active_status(self):
        """Test toggling a place's active status via checkbox"""
        # Navigate to the place detail page
        self.driver.get(f"{self.live_server_url}/sensors/{self.place.slug}/")

        # Find the active checkbox
        active_checkbox = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".active-checkbox"))
        )

        # Get initial status
        initial_status = active_checkbox.is_selected()

        # Click the checkbox to toggle status
        active_checkbox.click()

        # Wait for the AJAX request to complete
        time.sleep(1)  # Simple wait, could be improved with explicit waits

        # Refresh the page to verify the change persisted
        self.driver.refresh()

        # Find the checkbox again and check its status
        active_checkbox = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".active-checkbox"))
        )

        # Verify the status changed
        self.assertNotEqual(initial_status, active_checkbox.is_selected())

    @unittest.skip("Requires browser and server running")
    def test_location_active_status_affects_device_form(self):
        """Test that changing a location's active status affects device creation form"""
        # Navigate to the location detail page
        self.driver.get(f"{self.live_server_url}/sensors/{self.place.slug}/location/{self.location.pk}/")

        # Find and click the active checkbox to deactivate the location
        active_checkbox = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".active-checkbox"))
        )

        # Ensure location is active initially
        if not active_checkbox.is_selected():
            active_checkbox.click()
            time.sleep(1)  # Wait for AJAX
            self.driver.refresh()
            active_checkbox = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".active-checkbox"))
            )

        # Now deactivate the location
        active_checkbox.click()
        time.sleep(1)  # Wait for AJAX

        # Navigate to device creation form
        self.driver.get(
            f"{self.live_server_url}/sensors/{self.place.slug}/location/{self.location.pk}/device/create/"
        )

        # Check if the device active checkbox is disabled
        device_active_checkbox = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='is_active']"))
        )

        # Verify the checkbox is disabled when location is inactive
        self.assertFalse(device_active_checkbox.is_enabled())

    @unittest.skip("Requires browser and server running")
    def test_device_active_status_affects_sensor_form(self):
        """Test that changing a device's active status affects sensor creation form"""
        # Navigate to the device detail page
        self.driver.get(f"{self.live_server_url}/sensors/{self.place.slug}/device/{self.device.pk}/")

        # Find and click the active checkbox to deactivate the device
        active_checkbox = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".active-checkbox"))
        )

        # Ensure device is active initially
        if not active_checkbox.is_selected():
            active_checkbox.click()
            time.sleep(1)  # Wait for AJAX
            self.driver.refresh()
            active_checkbox = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".active-checkbox"))
            )

        # Now deactivate the device
        active_checkbox.click()
        time.sleep(1)  # Wait for AJAX

        # Navigate to sensor creation form
        self.driver.get(
            f"{self.live_server_url}/sensors/{self.place.slug}/device/{self.device.pk}/sensor/create/"
        )

        # Check if the sensor active checkbox is disabled
        sensor_active_checkbox = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='is_active']"))
        )

        # Verify the checkbox is disabled when device is inactive
        self.assertFalse(sensor_active_checkbox.is_enabled())

    @unittest.skip("Requires browser and server running")
    def test_data_store_changes_form_fields(self):
        """Test that changing the data store in sensor form shows/hides appropriate fields"""
        # Navigate to the sensor creation form
        self.driver.get(
            f"{self.live_server_url}/sensors/{self.place.slug}/device/{self.device.pk}/sensor/create/"
        )

        # Find the data store select element
        data_store_select = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "select[name='data_store']"))
        )

        # Check initial state - InfluxDB fields should be hidden
        influx_fields = self.driver.find_element(By.CSS_SELECTOR, ".influx-fields")
        self.assertEqual(influx_fields.get_attribute("style"), "display: none;")

        # Select InfluxDB as data store
        from selenium.webdriver.support.ui import Select
        select = Select(data_store_select)
        select.select_by_value("INFLUX")

        # Check that InfluxDB fields are now visible
        WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".influx-fields"))
        )

        # Change back to API
        select.select_by_value("API")

        # Check that InfluxDB fields are hidden again
        WebDriverWait(self.driver, 10).until(
            lambda driver: driver.find_element(By.CSS_SELECTOR, ".influx-fields").get_attribute("style") == "display: none;"
        )
