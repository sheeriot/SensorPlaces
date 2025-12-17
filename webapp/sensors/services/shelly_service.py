import logging
import re
from collections import defaultdict
from django.conf import settings
from django.utils.text import slugify
from sensors.models import Device, DeviceType, Place, InfluxStore, Unit
from sensors.services.sensor_service import process_sensor_reading
from sensors.influx_client import write_to_influx
from icecream import ic
from sensors.utils import record_webhook_activity
from sensors.services.measurement_utils import get_influx_details
from django.http import HttpRequest
from django.utils import timezone
from django.db import transaction


logger = logging.getLogger(__name__)


# Map of known Shelly model identifiers to a canonical name and device type hint.
# Keys can be model names from User-Agent or prefixes from webhook URLs.
# All keys should be lowercase.
# Device types should match names in device_types.yaml
SHELLY_PRODUCT_MAP = {
    # Official Model IDs (from User-Agent)
    'shht-1': {'model': 'H&T G1', 'device_type': 'Environmental Sensor'},
    'shwt-1': {'model': 'Flood G1', 'device_type': 'Water Leak Sensor'},
    'htg3': {'model': 'H&T G3', 'device_type': 'Environmental Sensor'},
    'mini1pmg4': {'model': '1PM Mini G4', 'device_type': 'Smart Plug'},
    'floodsensorg4': {'model': 'Flood G4', 'device_type': 'Water Leak Sensor'},
}


def _is_mac_address(s: str) -> bool:
    """Checks if a string is a 6 or 12-character hex string."""
    if not isinstance(s, str):
        return False
    return len(s) in (6, 12) and all(c in '0123456789abcdefABCDEF' for c in s)


class ShellyService:
    def __init__(self, place: Place, influx_store: InfluxStore = None, request: HttpRequest = None):
        self.place = place
        # Use provided influx_store or fall back to the place's default
        self.influx_store = influx_store or place.default_influx_store
        self.request = request

        if not self.influx_store:
             ic(f"No default InfluxDB store configured for Place: {place.name}")

    def _extract_scrape_metadata(self, request: HttpRequest, params: dict) -> dict:
        """
        Extracts and returns a clean dictionary of metadata from the request
        and data payload, excluding sensor readings.
        """
        metadata = {}
        if not request:
            return metadata

        # Capture the full request URL and headers
        metadata['request_url'] = request.build_absolute_uri()
        metadata['request_headers'] = {k: v for k, v in request.headers.items()}

        # Get client IP from X-Forwarded-For header, fallback to REMOTE_ADDR
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            metadata['client_ip'] = x_forwarded_for.split(',')[0].strip()
        else:
            metadata['client_ip'] = request.META.get('REMOTE_ADDR')

        # Parse User-Agent for model and firmware
        metadata['model_name'] = None
        metadata['firmware_version'] = None
        user_agent = request.headers.get('User-Agent')
        if user_agent:
            if user_agent.startswith('Shelly/'):
                # Gen1 format: 'Shelly/20231107-162243/v1.14.1-rc1-g0617c15 (SHHT-1)'
                match = re.search(r'Shelly/([^ ]+) \(([^)]+)\)', user_agent)
                if match:
                    metadata['firmware_version'] = match.group(1)
                    metadata['model_name'] = match.group(2)
            elif '(ShellyOS)' in user_agent:
                # Gen2 format: 'HTG3/1.7.1 (ShellyOS)'
                match = re.search(r'([^/]+)/([^\s]+)\s+\(ShellyOS\)', user_agent)
                if match:
                    metadata['model_name'] = match.group(1).strip()
                    version = match.group(2).strip()
                    metadata['firmware_version'] = f"ShellyOS {version}"

        # Get full device ID from payload
        full_device_id = params.get('id') or params.get('device_id') or params.get('src')
        if full_device_id:
            metadata['full_device_id'] = full_device_id

        return metadata

    def process_data(self, device_id: str, data: dict, request: HttpRequest = None):
        """
        Process Shelly data.
        """
        # if request:
        #     # ic(request.body)

        if not device_id:
            raise ValueError("Device identifier is missing from the request.")

        device = self._get_device_or_create(device_id, data, request)
        self._process_readings(device, data, request)
        return True

    @transaction.atomic
    def _get_device_or_create(self, device_id_str: str, data: dict = None, request: HttpRequest = None) -> Device:
        """
        Retrieves a device by its MAC address or creates it.

        This function performs the following steps:
        1. Parses a MAC address from the provided `device_id_str`.
        2. Attempts to find an existing device with that MAC address.
        3. If found, updates its `last_seen` time and returns it.
        4. If not found, creates a new device, determining its model and type
           from the request headers and URL using a standardized product map.
        """
        # ic("--- Shelly Service: Get or Create Device ---")
        # ic(f"Incoming device_id_str: '{device_id_str}'")

        # --- Step 1: Determine the canonical unique ID (the MAC address) ---
        parsed_id = None
        if _is_mac_address(device_id_str):
            parsed_id = device_id_str.lower()
        else:
            if '-' in device_id_str:
                potential_mac = device_id_str.split('-')[-1]
                if _is_mac_address(potential_mac):
                    parsed_id = potential_mac.lower()

        if not parsed_id:
            parsed_id = device_id_str.lower()
            logger.warning(
                f"Could not parse a MAC address from '{device_id_str}'. "
                f"Using the full string as the unique device_id."
            )
        # ic(f"Parsed device MAC: {parsed_id}")

        # --- Step 2: Attempt to find and update existing device ---
        device = Device.objects.select_for_update().filter(device_id=parsed_id).first()

        if device:
            # ic("Found existing device:", device.name, f"(ID: {device.id})")

            # Always update last_seen timestamp
            device.last_seen = timezone.now()

            # If a data scrape is requested, update device details
            if device.scrape_data and request:
                ic("scrape_data flag is True. Refreshing device metadata.")

                # Get new metadata. This will fully replace the old scraped_data.
                new_scraped_data = self._extract_scrape_metadata(request, data)
                raw_model_from_ua = new_scraped_data.pop('model_name', None)

                # Add timestamp and raw model name to the new metadata
                new_scraped_data['scraped_at'] = timezone.now().isoformat(timespec='seconds').replace('+00:00', 'Z')
                if raw_model_from_ua:
                    new_scraped_data['scraped_model_name'] = raw_model_from_ua

                # Directly replace the scraped_data
                device.scraped_data = new_scraped_data
                device.scrape_data = False  # Reset the flag

                # If we got a raw model, try to update the main device.model with the mapped "pretty" name
                if raw_model_from_ua:
                    lookup_key = raw_model_from_ua.lower().strip()
                    if lookup_key in SHELLY_PRODUCT_MAP:
                        product_info = SHELLY_PRODUCT_MAP[lookup_key]
                        device.model = product_info['model']
                        ic(f"Updated device model to mapped value '{device.model}'.")
                    else:
                        # Fallback to storing raw value if no map is found
                        device.model = raw_model_from_ua
                        ic(f"Could not map '{lookup_key}', updated device model to raw value '{device.model}'.")

            device.save()
            return device

        # --- Step 3: Device not found, proceed with creation ---
        ic("Device not found. Creating a new one.")

        scrape_metadata = self._extract_scrape_metadata(request, data)
        raw_model_from_ua = scrape_metadata.pop('model_name', None)

        # Prepare scraped_data, including the raw scraped model name
        scraped_data = scrape_metadata
        scraped_data['scraped_at'] = timezone.now().isoformat(timespec='seconds').replace('+00:00', 'Z')
        if raw_model_from_ua:
            scraped_data['scraped_model_name'] = raw_model_from_ua

        ic(f"Info from headers (User-Agent): model='{raw_model_from_ua}', firmware='{scraped_data.get('firmware_version')}'")

        # Determine model and type from our map
        # final_model_name is the "pretty" name for display and for generating the device_name
        final_model_name = "Shelly Device"  # Generic fallback
        device_type_name = "Shelly-TBD"    # Generic fallback

        # Prioritize User-Agent model name for lookup
        lookup_key = None
        if raw_model_from_ua:
            lookup_key = raw_model_from_ua.lower().strip()

        # If not found via User-Agent, try using the URL prefix
        if not lookup_key or lookup_key not in SHELLY_PRODUCT_MAP:
             if '-' in device_id_str:
                url_prefix = device_id_str.split('-')[0].lower()
                ic(f"User-Agent model not in map or not provided, trying URL prefix: '{url_prefix}'")
                if url_prefix in SHELLY_PRODUCT_MAP:
                    lookup_key = url_prefix

        if lookup_key and lookup_key in SHELLY_PRODUCT_MAP:
            product_info = SHELLY_PRODUCT_MAP[lookup_key]
            final_model_name = product_info['model']
            device_type_name = product_info['device_type']
            ic(f"Matched product using key '{lookup_key}': Mapped Model='{final_model_name}', Type='{device_type_name}'")
        else:
            ic(f"Could not map '{lookup_key or device_id_str}' to a known product. Using fallbacks.")

        # Use find_by_alias to match by name or alias (configurable in admin)
        device_type = DeviceType.find_by_alias(device_type_name)
        if not device_type:
            # Fallback to the TBD type if the specific one doesn't exist
            device_type = DeviceType.find_by_alias("Shelly-TBD")

        # Construct a standardized device name
        mac_suffix = parsed_id[-6:]
        if final_model_name != "Shelly Device":
            # Use the non-bracketed part of the model name for the device's name
            base_model_name = final_model_name.split('(')[0].strip()
            # e.g. "shelly-h-t-g1-abcdef"
            base_name = slugify(base_model_name.replace("Shelly", "")).strip("-")
            device_name = f"shelly-{base_name}-{mac_suffix}"
        else:
            # e.g. "shelly-abcdef"
            device_name = f"shelly-{mac_suffix}"
        ic(f"Constructed device name: {device_name}")

        unassigned_location = self.place.get_unassigned_location()

        defaults = {
            'name': device_name,
            'location': unassigned_location,
            'manufacturer': "Shelly",
            'model': final_model_name, # Store the mapped, "pretty" model name
            'device_type': device_type,
            'is_active': False,  # Require manual activation for new devices
            'scraped_data': scraped_data,
            'last_seen': timezone.now()
        }

        # Create the device
        device = Device.objects.create(device_id=parsed_id, **defaults)

        client_ip = scraped_data.get('client_ip', 'N/A')
        message = (
            f"WEBHOOK: New Device | Place: {self.place.name} | "
            f"Device: {device.name} | ID: {parsed_id} | IP: {client_ip} | Model: {final_model_name}"
        )
        record_webhook_activity(message)
        ic(f"CREATED new device: {device.name} ({device.id})")

        return device

    def _process_readings(self, device: Device, params: dict, request: HttpRequest = None):
        # Always update the client_ip if it has changed.
        client_ip = device.scraped_data.get('client_ip')
        needs_save = False
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                current_ip = x_forwarded_for.split(',')[0].strip()
            else:
                current_ip = request.META.get('REMOTE_ADDR')

            if current_ip and current_ip != client_ip:
                device.scraped_data['client_ip'] = current_ip
                client_ip = current_ip # Use the new IP immediately for logging
                needs_save = True

        # The logic for scrape_data is now handled in _get_device_or_create
        if needs_save:
            device.save(update_fields=['scraped_data'])

        # Create a mutable copy of the parameters to allow modification.
        processed_params = params.copy()

        # Handle boolean values for Switch type
        if 'switch' in processed_params:
            if processed_params['switch'].lower() == 'on':
                processed_params['switch'] = True
            elif processed_params['switch'].lower() == 'off':
                processed_params['switch'] = False

        # Handle boolean values for Water/Flood detectors from 'true'/'false' strings
        for key in ['water', 'flood']:
            if key in processed_params:
                value = processed_params[key]
                if isinstance(value, str):
                    if value.lower() == 'true':
                        processed_params[key] = True
                    elif value.lower() == 'false':
                        processed_params[key] = False

        # Keys to skip - these are metadata, not sensor readings
        skip_keys = {'id', 'device_id', 'src', 'device'}

        client_ip_for_log = client_ip or 'N/A'
        # Dict to hold readings grouped by target Influx measurement
        grouped_readings = defaultdict(lambda: {'fields': {}, 'sensors': []})
        processed_sensors = []

        for key, value in processed_params.items():
            if key in skip_keys:
                continue

            # The key itself (e.g., 'tempf', 'humidity', 'batV') is used as the measurement_name
            # SensorType.find_by_alias() will match it against aliases in sensor_types.yaml
            measurement_name = key
            value_to_store = value

            # If not a boolean, process as a float
            if not isinstance(value_to_store, bool):
                try:
                    if isinstance(value, str):
                        if value.lower() == 'true':
                            value_to_store = 1.0
                        elif value.lower() == 'false':
                            value_to_store = 0.0
                        else:
                            value_to_store = float(value)
                    else:
                        value_to_store = float(value)
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert Shelly value '{value}' for '{key}' to float.")
                    continue

            # If Influx is configured, we will still update the cache but not create a new local DB reading.
            update_cache_only = bool(self.influx_store)

            sensor_obj = process_sensor_reading(
                device,
                measurement_name,
                value_to_store,
                source='shelly-webhook',
                skip_local_storage=update_cache_only,
                reading_key=key  # Store the original key for future matching
            )
            processed_sensors.append({'sensor': sensor_obj, 'value': value_to_store, 'name': measurement_name})

            if not sensor_obj:
                continue

            # Group for InfluxDB if source is configured
            if self.influx_store:
                # If the sensor has a specific measurement set, use it. Otherwise, determine from SensorType.
                if sensor_obj.influx_measurement:
                    influx_measurement = sensor_obj.influx_measurement
                    influx_field = sensor_obj.influx_field_name or 'value'
                elif sensor_obj.sensor_type:
                    # Use SensorType's configured influx settings
                    influx_details = get_influx_details(sensor_obj.sensor_type)
                    if influx_details:
                        influx_measurement, influx_field = influx_details
                    else:
                        # Fallback for unmapped types
                        influx_measurement = slugify(sensor_obj.sensor_type.name)
                        influx_field = slugify(sensor_obj.sensor_type.name)
                        ic(f"WARNING: No Influx mapping for SensorType '{sensor_obj.sensor_type.name}'. Using fallback: M='{influx_measurement}', F='{influx_field}'")
                else:
                    # No sensor_type - use raw key as fallback
                    influx_measurement = slugify(measurement_name)
                    influx_field = slugify(measurement_name)
                    ic(f"WARNING: No SensorType for '{measurement_name}'. Using fallback: M='{influx_measurement}', F='{influx_field}'")

                grouped_readings[influx_measurement]['fields'][influx_field] = value_to_store
                # Store the sensor and its intended influx field for potential update
                grouped_readings[influx_measurement]['sensors'].append({'sensor': sensor_obj, 'field': influx_field, 'measurement': influx_measurement})

        # Write grouped readings to InfluxDB
        if self.influx_store:
            for measurement_group, data in grouped_readings.items():
                fields = data['fields']
                sensors_info = data['sensors']
                tags = {'device_id': device.device_id, 'device_name': slugify(device.name)}

                try:
                    write_to_influx(self.influx_store, measurement_group, fields, tags)
                    storage_status = "Stored"

                    # Update Sensor Configuration on Success
                    for info in sensors_info:
                        sensor = info['sensor']

                        if not sensor.influx_store:
                            sensor.influx_store = self.influx_store
                        if not sensor.influx_measurement:
                            sensor.influx_measurement = info['measurement']
                        if not sensor.influx_field_name:
                            sensor.influx_field_name = info['field']
                        if not sensor.influx_tag_key:
                            sensor.influx_tag_key = 'device_id'

                        if sensor.data_store != 'INFLUX':
                            sensor.data_store = 'INFLUX'

                        sensor.save(update_fields=['influx_store', 'influx_measurement', 'influx_field_name', 'influx_tag_key', 'data_store'])

                except Exception as e:
                    storage_status = "Failed"
                    logger.error(f"Influx Error for measurement '{measurement_group}': {e}")
                    # Ensure fallback to DIRECT on failure
                    for info in sensors_info:
                        sensor = info['sensor']
                        if sensor.data_store == 'INFLUX':
                             sensor.data_store = 'DIRECT'
                             sensor.save(update_fields=['data_store'])

                # Log the action for this group
                if settings.WEBHOOK_SNIFFER:
                    field_str = ", ".join([f"{k}={v}" for k, v in fields.items()])
                    action_msg = f"Influx {storage_status}, cached."
                    message = f"WEBHOOK: Reading | Place: {self.place.name} | Device: {device.name} | IP: {client_ip_for_log} | Measurement: {measurement_group} | Values: [{field_str}] | Action: {action_msg}"
                    record_webhook_activity(message)

        # Log readings that were not sent to InfluxDB
        for item in processed_sensors:
            sensor_obj = item['sensor']
            if not sensor_obj or (self.influx_store and get_influx_details(item['name'])):
                continue # Skip if sensor creation failed or if it was handled by grouped Influx logging

            storage_system = "Local"
            storage_status = "Stored" if sensor_obj else "Failed"
            cached_status = ", cached" if sensor_obj else ""

            if settings.WEBHOOK_SNIFFER:
                action_msg = f"{storage_system} {storage_status}{cached_status}."
                message = f"WEBHOOK: Reading | Place: {self.place.name} | Device: {device.name} | IP: {client_ip_for_log} | Sensor: {item['name']} | Value: {item['value']} | Action: {action_msg}"
                record_webhook_activity(message)
