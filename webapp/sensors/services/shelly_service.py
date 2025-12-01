import logging
from django.conf import settings
from django.utils.text import slugify
from sensors.models import Device, DeviceType, Place, InfluxSource, Unit
from sensors.services.sensor_service import process_sensor_reading
from sensors.influx_client import write_to_influx
from icecream import ic
from sensors.utils import record_webhook_activity

logger = logging.getLogger(__name__)

class ShellyService:
    def __init__(self, place: Place, influx_source: InfluxSource = None):
        self.place = place
        # Use provided influx_source or fall back to the place's default
        self.influx_source = influx_source or place.default_influx_source

        if not self.influx_source:
             ic(f"No default InfluxDB source configured for Place: {place.name}")

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
            device_name = f"{model_name or 'Device'} {display_id}".strip()

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

                # Check if we should skip local storage (if Influx source is available)
                skip_local = False
                if self.influx_source:
                    skip_local = True

                sensor_obj = process_sensor_reading(device, measurement_name, val_float, skip_local_storage=skip_local)

                # Special post-creation configuration for specific sensor types
                if sensor_obj:
                    # Flood -> Boolean Unit
                    if measurement_name == 'Water Detector' and not sensor_obj.unit:
                        bool_unit = Unit.objects.filter(name__iexact='Boolean').first()
                        if bool_unit:
                            sensor_obj.unit = bool_unit
                            sensor_obj.save(update_fields=['unit'])

                # Prepare for logging
                storage_system = "Local"
                storage_status = "Failed"
                cached_status = ""

                # Logic: If influx_source is present, we try to write.
                if self.influx_source:
                    storage_system = "Influx"
                    if sensor_obj:
                        # Write to Influx first to verify connectivity
                        measurement = sensor_obj.influx_measurement or f"{slugify(device.name)}_{slugify(sensor_obj.name)}"
                        fields = {'value': val_float}
                        tags = {'device_id': device.device_id, 'sensor': sensor_obj.name}

                        try:
                            write_to_influx(self.influx_source, measurement, fields, tags)
                            storage_status = "Stored"

                            # Update Sensor Configuration on Success
                            sensor_obj.influx_source = self.influx_source
                            sensor_obj.influx_measurement = measurement

                            st = sensor_obj.sensor_type
                            can_override = st.allow_override if st else True

                            if can_override:
                                sensor_obj.data_type = 'INFLUX'
                                sensor_obj.save()
                            else:
                                sensor_obj.save()

                        except Exception as e:
                            storage_status = "Failed"
                            logger.error(f"Influx Error: {e}")

                            # Ensure fallback to DIRECT on failure
                            if sensor_obj.data_type == 'INFLUX':
                                 sensor_obj.data_type = 'DIRECT'
                                 sensor_obj.save()
                else:
                    storage_system = "Local"
                    if sensor_obj:
                         storage_status = "Stored"

                # Determine cache status for log
                if sensor_obj:
                    cached_status = ", cached"
                else:
                    # If sensor_obj is None, process_sensor_reading failed
                    cached_status = ""

                # Log final state to icecream
                # if sensor_obj:
                #      ic(sensor_obj.__dict__)

                if settings.WEBHOOK_SNIFFER:
                    action_msg = f"{storage_system} {storage_status}{cached_status}."
                    message = f"WEBHOOK: Reading | Place: {self.place.name} | Device: {device.name} | Sensor: {measurement_name} | Value: {val_float} | Action: {action_msg}"
                    record_webhook_activity(message)
            else:
                pass
