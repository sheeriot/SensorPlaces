import os
import time
import inspect
from datetime import datetime, timezone
from django.test import TestCase
from django.conf import settings
from sensors.models import InfluxSource, Place
from sensors.influx_client import write_to_influx
from influxdb_client_3 import InfluxDBClient3, Point


class InfluxIntegrationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Load config directly from environment variables, as they are injected by Docker Compose
        cls.env_config = {
            'INFLUX_TEST_NAME': os.environ.get('INFLUX_TEST_NAME'),
            'INFLUX_TEST_URL': os.environ.get('INFLUX_TEST_URL'),
            'INFLUX_TEST_ORG': os.environ.get('INFLUX_TEST_ORG'),
            'INFLUX_TEST_BUCKET_NAME': os.environ.get('INFLUX_TEST_BUCKET_NAME'),
            'INFLUX_TEST_TOKEN': os.environ.get('INFLUX_TEST_TOKEN'),
        }

        if not cls.env_config.get('INFLUX_TEST_TOKEN'):
            print("WARNING: InfluxDB test config not found in environment variables. Tests will fail or be skipped.")

        # Use a fixed measurement name for all test runs
        cls.measurement = "django_test_measurement"

    def setUp(self):
        if not self.env_config.get('INFLUX_TEST_TOKEN'):
            self.skipTest("No InfluxDB configuration found")

        self.place = Place.objects.create(
            name="Test Place",
            address="123 Test St",
            latitude=0.0,
            longitude=0.0
        )
        self.influx_source = InfluxSource.objects.create(
            place=self.place,
            name=self.env_config.get('INFLUX_TEST_NAME', 'Test Source'),
            url=self.env_config.get('INFLUX_TEST_URL'),
            org=self.env_config.get('INFLUX_TEST_ORG'),
            bucket_name=self.env_config.get('INFLUX_TEST_BUCKET_NAME'),
            token=self.env_config.get('INFLUX_TEST_TOKEN')
        )

    def test_a_connection(self):
        """Test a) make sure we can connect"""
        print(f"\nTesting connection to {self.influx_source.url}...")
        client = InfluxDBClient3(
            host=self.influx_source.url,
            token=self.influx_source.token,
            org=self.influx_source.org,
            database=self.influx_source.bucket_name
        )
        try:
            # A simple query to check for connectivity without relying on specific tables.
            # Querying the information schema is a reliable way to do this.
            client.query("SELECT table_name FROM information_schema.tables", language="sql")
            print("Connection successful.")
            method = getattr(self, self._testMethodName)
            _, start_line = inspect.getsourcelines(method)
            print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")
        except Exception as e:
            self.fail(f"Connection failed: {e}")
        finally:
            client.close()

    def test_b_write_point(self):
        """Test b) make sure we can write an InfluxDB data point"""
        print(f"\nTesting write to measurement {self.measurement}...")
        fields = {"temperature": 25.5, "humidity": 60.0}
        tags = {"location": "lab_b"}

        try:
            write_to_influx(self.influx_source, self.measurement, fields, tags)
            print("Write successful.")
            method = getattr(self, self._testMethodName)
            _, start_line = inspect.getsourcelines(method)
            print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")
        except Exception as e:
            self.fail(f"Write failed: {e}")

    def test_c_read_data(self):
        """Test c) now read data from Influx"""
        print(f"\nTesting read from measurement {self.measurement}...")
        # Write some data first to ensure there's something to read
        fields = {"value": 100.0}
        tags = {"sensor": "sensor_c"}
        write_to_influx(self.influx_source, self.measurement, fields, tags)

        time.sleep(1) # Brief pause for data to be ingested and queryable

        client = InfluxDBClient3(
            host=self.influx_source.url,
            token=self.influx_source.token,
            org=self.influx_source.org,
            database=self.influx_source.bucket_name
        )

        try:
            query = f'SELECT * FROM "{self.measurement}" WHERE sensor=\'sensor_c\''
            reader = client.query(query=query, language="sql")
            df = reader.to_pandas()

            self.assertFalse(df.empty, "Query returned no data")
            self.assertTrue('value' in df.columns)
            self.assertEqual(float(df.iloc[0]['value']), 100.0)
            print(f"Read successful. Got: {df.iloc[0]['value']}")
            method = getattr(self, self._testMethodName)
            _, start_line = inspect.getsourcelines(method)
            print(f"==>> {self.__class__.__name__}: {self._testMethodName} (line {start_line}) -> PASS")

        except Exception as e:
            self.fail(f"Read failed: {e}")
        finally:
            client.close()
