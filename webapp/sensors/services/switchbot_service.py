import logging
import requests
from collections import defaultdict
from django.conf import settings
from django.utils.text import slugify
from sensors.models import Place, Device, Sensor
from sensors.services.sensor_service import process_sensor_reading
from sensors.influx_client import write_to_influx
from sensors.services.measurement_utils import get_influx_details
from icecream import ic

from .. import switchbot_client
from ..utils import write_sensor_reading_to_influx

logger = logging.getLogger(__name__)

# This key_map is now at the module level so it can be imported elsewhere
KEY_MAP = {
    'temperature': 'Temperature',
    'humidity': 'Humidity',
    'lightLevel': 'Light Level',
    'battery': 'Battery Level',
    'leakState': 'Water Detector',
    'moveDetected': 'Motion Detected',
}


class SwitchBotService:
    """
    Service to interact with the SwitchBot API and sync device data.
    """
    def __init__(self, place: Place):
        self.place = place
        if not place.switchbot_token:
            raise ValueError("SwitchBot token is not configured for this place.")
        self.token = place.switchbot_token
        self.secret = place.switchbot_secret
        # Use the dedicated influx source for switchbot, or fall back to the place's default, or None
        self.influx_source = place.switchbot_influx_source or place.default_influx_source

    def fetch_and_process_single_device_reading(self, device: Device):
        """
        Fetches the latest reading for a single SwitchBot device, updates the cache,
        creates a historical reading, and writes to InfluxDB if active.
        """
        ic(f"Service: Fetching single device reading for '{device.name}'")
        status_response = switchbot_client.get_status(device.device_id, self.token, self.secret)

        if status_response.get('statusCode') != 100:
            raise Exception(f"API error: {status_response.get('message', 'Unknown error')}")

        body = status_response.get('body', {})
        ic(f"Service: API response for {device.name}:", body)

        from sensors.models import SensorReading
        from django.utils import timezone

        readings_found = 0
        reading_map = {
            'temperature': ('Temperature', body.get('temperature')),
            'humidity': ('Humidity', body.get('humidity')),
            'battery': ('Battery', body.get('battery')),
        }

        for api_key, (sensor_type_name, value) in reading_map.items():
            if value is not None:
                try:
                    sensor = device.sensors.get(sensor_type__name__icontains=sensor_type_name)
                    ic(f"Service: Found sensor '{sensor.name}' for type '{sensor_type_name}' with value: {value}")

                    # Update cache
                    sensor.cached_reading_value = value
                    sensor.cached_reading_timestamp = timezone.now()
                    sensor.save(update_fields=['cached_reading_value', 'cached_reading_timestamp'])

                    # Create historical reading
                    SensorReading.objects.create(sensor=sensor, value=value)

                    # Write to InfluxDB (the function handles the `is_active` check)
                    write_sensor_reading_to_influx(sensor, value)

                    readings_found += 1
                except Sensor.DoesNotExist:
                    ic(f"Service: Sensor for type '{sensor_type_name}' not found for device '{device.name}'.")
                except Exception as e:
                    ic(f"Service: An unexpected error occurred processing '{sensor_type_name}': {e}")
                    # Re-raise or handle as appropriate
                    raise e

        return readings_found

    def get_live_reading_for_sensor(self, sensor: Sensor):
        """
        Gets a live value for a single SwitchBot sensor from the API.
        Does not save, just returns the value.
        """
        ic(f"Service: Getting live reading for sensor '{sensor.name}'")
        try:
            status_data = switchbot_client.get_status(sensor.device.device_id, self.token, self.secret)
            if status_data.get('statusCode') == 100:
                live_body = status_data.get('body', {})
                ic(f"Service: Live reading API success. Body: {live_body}")

                # Find the API key for our sensor type
                sensor_api_key = None
                for api_key, std_name in KEY_MAP.items():
                    if std_name.lower() == sensor.sensor_type.name.lower():
                        sensor_api_key = api_key
                        break

                ic(f"Service: Mapped sensor type '{sensor.sensor_type.name}' to API key '{sensor_api_key}'")

                if sensor_api_key and sensor_api_key in live_body:
                    return live_body[sensor_api_key]
            else:
                ic(f"Service: Live reading API returned status {status_data.get('statusCode')}: {status_data.get('message')}")
        except Exception as e:
            ic(f"Service: Error getting SwitchBot status for live reading: {e}")

        return None


    def sync_devices_status(self):
        """
        Fetches the status of all SwitchBot devices associated with the place
        and updates their sensor readings.
        """
        if not self.place.switchbot_enable or not self.place.switchbot_token:
            logger.info(f"SwitchBot integration not enabled for place: {self.place.name}")
            return

        switchbot_devices = Device.objects.filter(location__place=self.place, is_switchbot=True, is_active=True)
        if not switchbot_devices.exists():
            logger.info(f"No active SwitchBot devices found for place: {self.place.name}")
            return

        ic(f"Found {switchbot_devices.count()} active SwitchBot devices for {self.place.name}")

        for device in switchbot_devices:
            self._fetch_and_process_device_status(device)

    def _fetch_and_process_device_status(self, device: Device):
        """
        Fetches status for a single device and processes its sensor readings.
        """
        url = f"{self.api_base_url}/devices/{device.device_id}/status"
        try:
            # This part still uses raw requests. Let's change it to use the client.
            # response = requests.get(url, headers=self.api_headers, timeout=10)
            # response.raise_for_status()
            # data = response.json()
            data = switchbot_client.get_status(device.device_id, self.token, self.secret)

            if data.get('statusCode') == 100 and data.get('body'):
                body = data['body']
                self._process_readings(device, body)
            else:
                logger.error(f"Error from SwitchBot API for device {device.name}: {data.get('message')}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get status for SwitchBot device {device.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to get status for SwitchBot device {device.name} (client): {e}")

    def _process_readings(self, device: Device, data: dict, activate_sensors: bool = False):
        """
        Processes the status data and creates sensor readings.
        Example data: {'temperature': 25.0, 'humidity': 50, ...}
        """
        # ic(f"Processing SwitchBot readings for {device.name}: {data}")
        # ic(f"Influx source for this run: {self.influx_source.name if self.influx_source else 'None'}")

        grouped_readings = defaultdict(lambda: {'fields': {}, 'sensors': []})
        processed_sensors = []

        for key, value in data.items():
            if key in KEY_MAP:
                measurement_name = KEY_MAP[key]
                try:
                    val_float = float(value)

                    # If Influx is configured, we won't store locally.
                    skip_local = bool(self.influx_source)

                    sensor_obj = process_sensor_reading(
                        device=device,
                        measurement_type=measurement_name,
                        value=val_float,
                        skip_local_storage=skip_local,
                        activate_sensor=activate_sensors
                    )
                    # ic(f"Processed sensor object for '{measurement_name}': {sensor_obj}")
                    processed_sensors.append({'sensor': sensor_obj, 'value': val_float, 'name': measurement_name})

                    if not sensor_obj:
                        continue

                    # Group for InfluxDB if source is configured
                    if self.influx_source:
                        # ic(f"Influx source is configured, preparing to group '{measurement_name}' for InfluxDB.")
                        influx_details = get_influx_details(measurement_name)
                        # ic(f"Influx details for '{measurement_name}': {influx_details}")

                        # Custom logic for battery
                        if influx_details:
                            influx_group, influx_field = influx_details
                        else:
                            influx_group, influx_field = 'reading', 'value'

                        # ic(f"Grouping for Influx: measurement_group='{influx_group}', field='{influx_field}', value='{val_float}'")
                        # Use influx_group for the measurement name part
                        grouped_readings[influx_group]['fields'][influx_field] = val_float
                        grouped_readings[influx_group]['sensors'].append({'sensor': sensor_obj, 'field': influx_field})


                except (ValueError, TypeError):
                    logger.warning(f"Could not convert SwitchBot value '{value}' for '{key}' to float.")

        # ic(f"Grouped Influx readings to be written: {grouped_readings}")
        # Write grouped readings to InfluxDB
        if self.influx_source:
            # ic("Attempting to write grouped readings to InfluxDB...")
            for measurement_group, influx_data in grouped_readings.items():
                fields = influx_data['fields']
                sensor_field_map = influx_data['sensors']
                tags = {'device_id': device.device_id, 'device_name': slugify(device.name)}

                # Construct the full measurement name
                measurement = f"{slugify(device.name)}_{measurement_group}"

                try:
                    write_to_influx(self.influx_source, measurement, fields, tags)

                    # Update Sensor Configuration on Success
                    for item in sensor_field_map:
                        sensor = item['sensor']
                        field = item['field']
                        sensor.influx_source = self.influx_source
                        sensor.influx_measurement = measurement
                        sensor.influx_field_name = field
                        sensor.influx_tag_key = 'device_id'  # Set the default tag key
                        st = sensor.sensor_type
                        can_override = st.allow_override if st else True
                        if can_override:
                            sensor.data_type = 'INFLUX'
                        sensor.save()
                        # ic(f"Successfully configured sensor '{sensor.name}' for InfluxDB.")

                except Exception as e:
                    # ic(f"Influx write ERROR for measurement '{measurement}': {e}")
                    logger.error(f"Influx Error for measurement '{measurement}': {e}")
                    # Ensure fallback to DIRECT on failure
                    for item in sensor_field_map:
                        sensor = item['sensor']
                        if sensor.data_type == 'INFLUX':
                             sensor.data_type = 'DIRECT'
                             sensor.save()

        # Log readings that were not sent to InfluxDB
        for item in processed_sensors:
            sensor_obj = item['sensor']
            if not sensor_obj or (self.influx_source and get_influx_details(item['name'])):
                continue # Skip if sensor creation failed or if it was handled by grouped Influx logging

            # This block will now only be hit for non-influx data or if there's no influx source
            # The logging for influx data can be handled inside the influx write loop if needed.
            logger.info(f"Stored local reading for {device.name} - {item['name']}: {item['value']}")
