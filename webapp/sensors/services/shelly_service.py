import logging
from collections import defaultdict
from django.conf import settings
from django.utils.text import slugify
from sensors.models import Device, DeviceType, Place, InfluxStore, Unit
from sensors.services.sensor_service import process_sensor_reading
from sensors.influx_client import write_to_influx
from icecream import ic
from sensors.utils import record_webhook_activity
from sensors.services.measurement_utils import get_influx_details

logger = logging.getLogger(__name__)

class ShellyService:
    def __init__(self, place: Place, influx_store: InfluxStore = None):
        self.place = place
        # Use provided influx_store or fall back to the place's default
        self.influx_store = influx_store or place.default_influx_store

        if not self.influx_store:
             ic(f"No default InfluxDB store configured for Place: {place.name}")

    def process_data(self, device_id: str, data: dict):
        """
        Process Shelly data.
        """
        device = self._get_device_or_create(device_id, data)
        self._process_readings(device, data)
        return True

    def _get_device_or_create(self, device_id_str: str, data: dict = None) -> Device:
        """
        Helper to find a device by ID or suffix, or create it if not found.
        Parses Shelly IDs like 'shellyflood-FCF5C4B110A1'.
        Checks data for hints about device type (e.g. battery_voltage reading).
        """
        parsed_id = device_id_str
        model_name = None
        manufacturer = "Shelly"

        if '-' in device_id_str:
            parts = device_id_str.split('-')
            parsed_id = parts[-1]
            prefix = parts[0].lower()
            if 'flood' in prefix:
                model_name = "Flood"
            elif 'shelly1' in prefix:
                model_name = "1"
            elif 'plus' in prefix:
                model_name = "Plus"

        # Try to find device
        device = Device.objects.filter(
            location__place=self.place,
            device_id__iexact=device_id_str
        ).first()

        if not device and parsed_id != device_id_str:
             device = Device.objects.filter(
                location__place=self.place,
                device_id__iexact=parsed_id
            ).first()

        if not device:
            # Auto-create
            unassigned_location = self.place.get_unassigned_location()
            display_id = parsed_id[-6:]
            device_name = f"{model_name or 'Shelly'} {display_id}".strip()

            device_type = None
            if model_name == "Flood":
                 device_type = DeviceType.objects.filter(name__iexact="Water Detector").first()

            # Check data for hints if device_type not yet determined
            # If reading is called battery_voltage, we might infer a generic Battery-related device type
            # if we had one, but the user requested "Shelly-TBD" if unknown.
            if not device_type:
                device_type = DeviceType.objects.filter(name__iexact="Shelly-TBD").first()
                if not device_type:
                    # Optional: Create it if it doesn't exist, or fallback to something else
                    pass

            device = Device.objects.create(
                device_id=parsed_id,
                name=device_name,
                location=unassigned_location,
                manufacturer=manufacturer,
                model=model_name,
                device_type=device_type,
                is_active=False
            )
            # if settings.WEBHOOK_SNIFFER:
            #     ic(f"WEBHOOK: Created new device | Place: {self.place.name} | Device: {device.name} | ID: {parsed_id}")
            message = f"WEBHOOK: New Device | Place: {self.place.name} | Device: {device.name} | ID: {parsed_id}"
            record_webhook_activity(message)

        return device

    def _process_readings(self, device: Device, params: dict):
        key_map = {
            'power': 'Power',
            'apower': 'Power',
            'current': 'Current',
            'voltage': 'Voltage',
            'temperature': 'Temperature', 'temp': 'Temperature', 'humidity': 'Humidity', 'hum': 'Humidity',
            'pm2.5': 'PM2.5', 'pm25': 'PM2.5', 'battery': 'battery',
            'flood': 'Water Detector', 'batV': 'Battery Voltage'
        }

        # Dict to hold readings grouped by target Influx measurement
        grouped_readings = defaultdict(lambda: {'fields': {}, 'sensors': []})
        processed_sensors = []

        for key, value in params.items():
            if key in ['id', 'device_id', 'src', 'device']:
                continue

            if key in key_map:
                try:
                    if isinstance(value, str):
                        if value.lower() == 'true':
                            val_float = 1.0
                        elif value.lower() == 'false':
                            val_float = 0.0
                        else:
                            val_float = float(value)
                    else:
                        val_float = float(value)
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert Shelly value '{value}' for '{key}' to float.")
                    continue

                measurement_name = key_map[key]

                # Special Battery Logic
                if measurement_name == 'battery':
                    if val_float > 25:
                        measurement_name = 'Battery Level'
                    else:
                        measurement_name = 'Battery Voltage'

                # If Influx is configured, we won't store locally.
                skip_local = bool(self.influx_store)

                sensor_obj = process_sensor_reading(device, measurement_name, val_float, skip_local_storage=skip_local)
                processed_sensors.append({'sensor': sensor_obj, 'value': val_float, 'name': measurement_name})

                if not sensor_obj:
                    continue

                # Special post-creation configuration for specific sensor types
                if measurement_name == 'Water Detector' and not sensor_obj.unit:
                    bool_unit = Unit.objects.filter(name__iexact='Boolean').first()
                    if bool_unit:
                        sensor_obj.unit = bool_unit
                        sensor_obj.save(update_fields=['unit'])

                # Group for InfluxDB if source is configured
                if self.influx_store:
                    # If the sensor has a specific measurement set, use it. Otherwise, determine from type.
                    if sensor_obj.influx_measurement:
                        influx_measurement = sensor_obj.influx_measurement
                        influx_field = sensor_obj.influx_field_name or get_influx_details(measurement_name)[1]
                    else:
                        influx_details = get_influx_details(measurement_name)
                        if influx_details:
                            influx_measurement, influx_field = influx_details
                        else:
                            # Skip if no mapping is found for this sensor type
                            continue
                    
                    grouped_readings[influx_measurement]['fields'][influx_field] = val_float
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

                    # Update Sensor Configuration on Success, but only if not already set
                    for info in sensors_info:
                        sensor = info['sensor']
                        
                        # Only set these if they are not already configured.
                        if not sensor.influx_store:
                            sensor.influx_store = self.influx_store
                        if not sensor.influx_measurement:
                            sensor.influx_measurement = info['measurement']
                        if not sensor.influx_field_name:
                            sensor.influx_field_name = info['field']
                        if not sensor.influx_tag_key:
                            sensor.influx_tag_key = 'device_id'
                        
                        # Data type can still be overridden
                        st = sensor.sensor_type
                        can_override = st.allow_override if st else True
                        if can_override and sensor.data_type != 'INFLUX':
                            sensor.data_type = 'INFLUX'
                        
                        sensor.save()

                except Exception as e:
                    storage_status = "Failed"
                    logger.error(f"Influx Error for measurement '{measurement_group}': {e}")
                    # Ensure fallback to DIRECT on failure
                    for info in sensors_info:
                        sensor = info['sensor']
                        if sensor.data_type == 'INFLUX':
                             sensor.data_type = 'DIRECT'
                             sensor.save()

                # Log the action for this group
                if settings.WEBHOOK_SNIFFER:
                    field_str = ", ".join([f"{k}={v}" for k, v in fields.items()])
                    action_msg = f"Influx {storage_status}, cached."
                    message = f"WEBHOOK: Reading | Place: {self.place.name} | Device: {device.name} | Measurement: {measurement_group} | Values: [{field_str}] | Action: {action_msg}"
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
                message = f"WEBHOOK: Reading | Place: {self.place.name} | Device: {device.name} | Sensor: {item['name']} | Value: {item['value']} | Action: {action_msg}"
                record_webhook_activity(message)
