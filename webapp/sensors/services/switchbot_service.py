import logging
import requests
from collections import defaultdict
from django.conf import settings
from django.utils.text import slugify
from sensors.models import Place, Device, Sensor, DeviceType
from sensors.services.sensor_service import process_sensor_reading
from sensors.influx_client import write_to_influx
from sensors.services.measurement_utils import get_influx_details
from icecream import ic

from .. import switchbot_client
from ..utils import write_sensor_reading_to_influx, record_webhook_activity

logger = logging.getLogger(__name__)

# Primary key ranges for data classification:
# - System seed data: pk < 100
# - User-created data: pk >= 100 and < 1000
# - Auto-created data (by webhooks/APIs): pk >= 1000
AUTO_CREATED_PK_START = 1000


def _get_next_auto_pk(model_class):
    """
    Get the next available primary key >= AUTO_CREATED_PK_START for auto-created records.
    """
    max_pk = model_class.objects.filter(pk__gte=AUTO_CREATED_PK_START).order_by('-pk').values_list('pk', flat=True).first()
    if max_pk is None:
        return AUTO_CREATED_PK_START
    return max_pk + 1


def get_or_create_auto_device_type(name: str, defaults: dict = None) -> DeviceType:
    """
    Get an existing DeviceType by name or alias (case-insensitive) or create a new one
    with pk >= 1000 for auto-created types.

    Uses the database aliases field for matching, making type resolution configurable
    by administrators without code changes.
    """
    # First try to find an existing one by name or alias
    device_type = DeviceType.find_by_alias(name)
    if device_type:
        return device_type

    # Create a new one with pk >= 1000
    next_pk = _get_next_auto_pk(DeviceType)
    create_kwargs = {
        'id': next_pk,
        'name': name,
        'description': f'Auto-created device type for {name}',
        'icon': 'bi-robot',
        'is_system': False,  # User/auto-created, not system
    }
    if defaults:
        create_kwargs.update(defaults)

    device_type = DeviceType.objects.create(**create_kwargs)
    ic(f"Auto-created DeviceType '{name}' with pk={next_pk}")
    return device_type

# This key_map is now at the module level so it can be imported elsewhere
# These map SwitchBot API field names to our standardized SensorType names
KEY_MAP = {
    'temperature': 'Temperature',
    'humidity': 'Humidity',
    'lightLevel': 'Ambient Light',  # Matches sensor_types.yaml
    'battery': 'Battery Level',
    'leakState': 'Leak Detected',  # Matches sensor_types.yaml
    'moveDetected': 'Motion',  # Consolidated in sensor_types.yaml
}


class SwitchBotService:
    """
    Service to interact with the SwitchBot API and sync device data.
    """
    def __init__(self, place: Place):
        self.place = place
        self.token = place.switchbot_token
        self.secret = place.switchbot_secret

        # Prioritize the SwitchBot-specific store, then fall back to the place's default
        self.influx_store = place.switchbot_influx_store or place.default_influx_store

        if not self.token or not self.secret:
            logger.warning(f"SwitchBot service for place {place.name} is missing API credentials.")

    def get_live_reading_for_sensor(self, sensor: Sensor):
        """
        Gets a live value for a single SwitchBot sensor from the API,
        but updates all sensors on the same device from the single API call.
        """
        ic("SWITCHBOT_SERVICE: Getting live reading from API and updating all related sensors")
        ic(f"Service: Triggered by sensor '{sensor.name}'")
        device = sensor.device

        try:
            status_data = switchbot_client.get_status(device.device_id, self.token, self.secret)
            if status_data.get('statusCode') == 100:
                live_body = status_data.get('body', {})
                ic(f"Service: Live reading API success for device {device.name}. Body: {live_body}")

                # Now, iterate over all sensors on this device and update them
                for sensor_to_update in device.sensors.all():
                    sensor_api_key = sensor_to_update.reading_key
                    if not sensor_api_key:
                        # Fallback logic to find the key if not explicitly set
                        sensor_type_name = sensor_to_update.sensor_type.name.lower()
                        if sensor_type_name in ('battery level', 'battery voltage'):
                            sensor_api_key = 'battery'
                        else:
                            for api_key, std_name in KEY_MAP.items():
                                if std_name.lower() == sensor_type_name:
                                    sensor_api_key = api_key
                                    break

                    if sensor_api_key and sensor_api_key in live_body:
                        value = live_body[sensor_api_key]
                        ic(f"Service: Updating sensor '{sensor_to_update.name}' with value '{value}' for key '{sensor_api_key}'")

                        # Use the existing service to process the reading
                        # This updates the sensor's cache fields
                        process_sensor_reading(
                            device=device,
                            measurement_type=sensor_to_update.sensor_type.name,
                            value=value,
                            source='switchbot-api-live',
                            skip_local_storage=bool(self.influx_store),
                            activate_sensor=False, # We are not activating sensors here
                            reading_key=sensor_api_key
                        )

                        # Write to InfluxDB for historical storage if configured
                        if sensor_to_update.data_store == 'INFLUX' and self.influx_store:
                            try:
                                write_sensor_reading_to_influx(sensor_to_update, float(value))
                                ic(f"Service: Wrote '{sensor_to_update.name}' value {value} to InfluxDB")
                            except Exception as e:
                                ic(f"Service: Failed to write '{sensor_to_update.name}' to InfluxDB: {e}")

                # Return the value for the originally requested sensor
                original_sensor_api_key = sensor.reading_key or \
                                          next((k for k, v in KEY_MAP.items() if v.lower() == sensor.sensor_type.name.lower()), None)

                return live_body.get(original_sensor_api_key)

            else:
                ic(f"Service: Live reading API returned status {status_data.get('statusCode')}: {status_data.get('message')}")
        except Exception as e:
            ic(f"Service: Error getting SwitchBot status for live reading: {e}")

        return None


    def import_device(self, device_id: str, device_name_from_form: str, location, is_active: bool):
        """
        Imports a new device from the SwitchBot API, creating the device
        and its associated sensors.
        """
        # 1. Fetch device status from API
        status_data = switchbot_client.get_status(device_id, self.token, self.secret)
        if status_data.get('statusCode') != 100:
            raise Exception(f"API Error: {status_data.get('message', 'Unknown error')}")

        body = status_data.get('body', {})

        # Use the name from the form, fall back to API, then to device_id
        device_name = device_name_from_form or body.get('deviceName') or device_id
        device_type_name = body.get('deviceType', 'SwitchBot Device')

        # 2. Create DeviceType (auto-created types get pk >= 1000)
        device_type = get_or_create_auto_device_type(
            device_type_name,
            defaults={'icon': 'bi-robot'}
        )

        # 3. Create or Update the Device
        device, created = Device.objects.update_or_create(
            device_id=device_id,
            defaults={
                'name': device_name,
                'is_switchbot': True,
                'is_active': is_active,
                'device_type': device_type,
                'location': location,
                'model': device_type_name,
                'manufacturer': 'SwitchBot'
            }
        )

        # 4. Create sensors and process initial readings
        from ..models import SensorType, SensorReading

        grouped_readings = defaultdict(lambda: {'fields': {}, 'sensors': []})
        imported_sensors = []

        for key, value in body.items():
            if key not in KEY_MAP:
                continue

            measurement_name = KEY_MAP[key]
            try:
                val_float = float(value)

                # Remap battery to Battery Level or Battery Voltage based on value
                if key == 'battery':
                    if val_float > 50:
                        measurement_name = 'Battery Level'
                    else:
                        measurement_name = 'Battery Voltage'

                # Only import sensors that have a matching SensorType with alias
                sensor_type = SensorType.find_by_alias(measurement_name)
                if not sensor_type:
                    logger.info(f"Skipping sensor '{measurement_name}' - no matching SensorType found")
                    continue

                # When importing, we want to activate the sensor based on the form input
                # And we skip local storage if an InfluxDB is configured, because the reading
                # will be stored there. The cache on the sensor is still updated.
                skip_local = bool(self.influx_store)

                sensor_obj = process_sensor_reading(
                    device=device,
                    measurement_type=measurement_name,
                    value=val_float,
                    source='switchbot-import',
                    skip_local_storage=skip_local,
                    activate_sensor=is_active,
                    reading_key=key
                )

                if not sensor_obj:
                    continue

                imported_sensors.append(sensor_obj)

                # Group for InfluxDB if source is configured
                if self.influx_store:
                    # Use the SensorType object to get InfluxDB details from database
                    influx_details = get_influx_details(sensor_type)

                    if influx_details:
                        influx_measurement, influx_field = influx_details
                    else:
                        # Fallback for unmapped types
                        influx_measurement, influx_field = 'reading', 'value'

                    grouped_readings[influx_measurement]['fields'][influx_field] = val_float
                    grouped_readings[influx_measurement]['sensors'].append({'sensor': sensor_obj, 'field': influx_field})

            except (ValueError, TypeError):
                logger.warning(f"Could not convert SwitchBot value '{value}' for '{key}' to float during import.")

        # Write grouped readings to InfluxDB
        if self.influx_store:
            for measurement_group, influx_data in grouped_readings.items():
                fields = influx_data['fields']
                sensor_field_map = influx_data['sensors']
                tags = {'device_id': device.device_id, 'device_name': slugify(device.name)}

                # Construct the full measurement name
                measurement = measurement_group

                try:
                    # Write the initial reading to InfluxDB
                    write_to_influx(self.influx_store, measurement, fields, tags)

                    # On success, configure the sensor to use InfluxDB for future readings
                    for item in sensor_field_map:
                        sensor = item['sensor']
                        field = item['field']
                        sensor.influx_store = self.influx_store
                        sensor.influx_measurement = measurement
                        sensor.influx_field_name = field
                        sensor.influx_tag_key = 'device_id'
                        sensor.data_store = 'INFLUX' # Set data store to INFLUX
                        sensor.save()

                except Exception as e:
                    logger.error(f"Influx Error for measurement '{measurement}' during import: {e}")
                    # On failure, ensure sensors are set to DIRECT storage
                    for item in sensor_field_map:
                        sensor = item['sensor']
                        if sensor.data_store == 'INFLUX':
                             sensor.data_store = 'NONE'
                             sensor.save()

        ic(f"Finished import. Total sensors processed: {len(imported_sensors)}")
        return device, imported_sensors, body

    def write_webhook_data(self, device: Device, fields: dict):
        """
        Writes a dictionary of sensor fields from a webhook to InfluxDB.
        """
        if not self.influx_store:
            ic(f"SwitchBot service for place {self.place.name} has no InfluxDB store configured for writing.")
            return

        for field, value in fields.items():
            tags = {'device_id': device.device_id, 'device_name': slugify(device.name)}
            # The measurement name is now just the field name (e.g., 'temperature', 'humidity')
            measurement = field

            # The value needs to be in a dictionary, with a key like 'value'
            field_data = {'value': value}

            try:
                write_to_influx(self.influx_store, measurement, field_data, tags)
                ic(f"Successfully wrote webhook data for {device.name} to InfluxDB measurement {measurement}.")
            except Exception as e:
                logger.error(f"Failed to write SwitchBot webhook data to InfluxDB for device '{device.device_id}', measurement '{measurement}': {e}")
                # Optionally re-raise or handle the exception as needed
                raise e


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
        grouped_readings = defaultdict(lambda: {'fields': {}, 'sensors': []})
        processed_sensors = []

        for key, value in data.items():
            if key in KEY_MAP:
                measurement_name = KEY_MAP[key]
                try:
                    val_float = float(value)

                    # If Influx is configured, we won't store locally.
                    skip_local = bool(self.influx_store)

                    sensor_obj = process_sensor_reading(
                        device=device,
                        measurement_type=measurement_name,
                        value=val_float,
                        source='switchbot-api',
                        skip_local_storage=skip_local,
                        activate_sensor=activate_sensors,
                        reading_key=key
                    )
                    processed_sensors.append({'sensor': sensor_obj, 'value': val_float, 'name': measurement_name})

                    if not sensor_obj:
                        continue

                    # Group for InfluxDB if source is configured
                    if self.influx_store:
                        influx_details = get_influx_details(measurement_name)

                        # Custom logic for battery
                        if influx_details:
                            influx_group, influx_field = influx_details
                        else:
                            influx_group, influx_field = 'reading', 'value'

                        grouped_readings[influx_group]['fields'][influx_field] = val_float
                        grouped_readings[influx_group]['sensors'].append({'sensor': sensor_obj, 'field': influx_field})


                except (ValueError, TypeError):
                    logger.warning(f"Could not convert SwitchBot value '{value}' for '{key}' to float.")

        # Write grouped readings to InfluxDB
        if self.influx_store:
            for measurement_group, influx_data in grouped_readings.items():
                fields = influx_data['fields']
                sensor_field_map = influx_data['sensors']
                tags = {'device_id': device.device_id, 'device_name': slugify(device.name)}

                # Construct the full measurement name
                measurement = measurement_group

                try:
                    write_to_influx(self.influx_store, measurement, fields, tags)

                    # Update Sensor Configuration on Success
                    for item in sensor_field_map:
                        sensor = item['sensor']
                        field = item['field']
                        sensor.influx_store = self.influx_store
                        sensor.influx_measurement = measurement
                        sensor.influx_field_name = field
                        sensor.influx_tag_key = 'device_id'  # Set the default tag key
                        st = sensor.sensor_type
                        can_override = st.allow_override if st else True
                        if can_override:
                            sensor.data_store = 'INFLUX'
                        sensor.save()

                except Exception as e:
                    logger.error(f"Influx Error for measurement '{measurement}': {e}")
                    # Ensure fallback to DIRECT on failure
                    for item in sensor_field_map:
                        sensor = item['sensor']
                        if sensor.data_store == 'INFLUX':
                             sensor.data_store = 'NONE'
                             sensor.save()

        # Log readings that were not sent to InfluxDB
        for item in processed_sensors:
            sensor_obj = item['sensor']
            if not sensor_obj or (self.influx_store and get_influx_details(item['name'])):
                continue # Skip if sensor creation failed or if it was handled by grouped Influx logging

            # This block will now only be hit for non-influx data or if there's no influx source
            # The logging for influx data can be handled inside the influx write loop if needed.
            logger.info(f"Stored local reading for {device.name} - {item['name']}: {item['value']}")
