import json
from uuid import UUID
import logging
from django.conf import settings
from django.http import HttpResponse, HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import os
from datetime import datetime
from icecream import ic

from sensors.models import Place, Device, Sensor, SensorReading, Location, InfluxSource, SensorType, DeviceType
from ..influx_client import write_to_influx

logger = logging.getLogger(__name__)

# --- Webhook Activity Recording ---
LOGS_DIR = os.path.join(settings.BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)
WEBHOOK_RECORD_FILE = os.path.join(LOGS_DIR, 'WEBHOOK_ACTIVITY.log')

def record_webhook_activity(message: str):
    """Appends a message to the webhook activity log file if WEBHOOK_SNIFFER is True."""
    if settings.WEBHOOK_SNIFFER:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        try:
            with open(WEBHOOK_RECORD_FILE, 'a') as f:
                f.write(f"{now_str} | {message}\n")
        except Exception as e:
            logger.error(f"Failed to write to webhook record file: {e}")
# --- End of Webhook Activity Recording ---

def process_sensor_reading(device: Device, measurement_type: str, value: float):
    """
    Helper to store sensor reading in local DB. Finds or creates a sensor.
    Returns the sensor object on success, None otherwise.
    """
    try:
        # Try to find a sensor with a type matching the measurement name
        sensor = Sensor.objects.filter(
            device=device,
            sensor_type__name__iexact=measurement_type
        ).first()

        # If not found, try matching by sensor name directly
        if not sensor:
            sensor = Sensor.objects.filter(
                device=device,
                name__iexact=measurement_type
            ).first()

        created = False
        if not sensor:
            sensor_type = SensorType.objects.filter(name__iexact=measurement_type).first()
            sensor_name = measurement_type.title()

            sensor = Sensor.objects.create(
                device=device,
                name=sensor_name,
                sensor_type=sensor_type,
                is_active=device.is_active,
                data_type='DIRECT',
                data_type_override=bool(sensor_type)  # Only override if a type is found
            )
            created = True
            if settings.WEBHOOK_SNIFFER:
                ic(f"Created new sensor '{sensor.name}' for device '{device.name}'")

        if sensor:
            # Determine value_boolean if reading is 0.0 or 1.0
            val_bool = None
            if value == 1.0:
                val_bool = True
            elif value == 0.0:
                val_bool = False

            SensorReading.objects.create(
                sensor=sensor,
                value=value,
                value_boolean=val_bool
            )
            from django.utils import timezone
            sensor.cached_reading_value = value
            sensor.cached_reading_timestamp = timezone.now()
            sensor.last_checked_timestamp = timezone.now()
            sensor.save(update_fields=['cached_reading_value', 'cached_reading_timestamp', 'last_checked_timestamp'])

            if created:
                place = device.location.place
                message = f"WEBHOOK: New Sensor | Place: {place.name} | Device: {device.name} | Sensor: {sensor.name}"
                record_webhook_activity(message)

            return sensor

        return None

    except Exception as e:
        logger.error(f"Error saving local sensor reading for {device.name}: {e}")
        return None

@method_decorator(csrf_exempt, name='dispatch')
class WebhookReceiverView(View):
    """
    Handles incoming webhooks from generic devices.
    """
    def post(self, request: HttpRequest, place_slug: str, uuid: UUID) -> HttpResponse:
        try:
            place = Place.objects.get(slug=place_slug)
            influx_source = InfluxSource.objects.filter(place=place).first()
        except Place.DoesNotExist:
            return HttpResponse(f"Place '{place_slug}' not found.", status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse("Invalid JSON", status=400)

        device_id = data.get('device_id')
        if not device_id:
            return HttpResponse("No device_id provided in payload.", status=400)

        try:
            device = Device.objects.get(device_id__iexact=device_id, location__place=place)
        except Device.DoesNotExist:
            return HttpResponse(f"Device '{device_id}' not found.", status=404)

        if 'sensors' in data and isinstance(data['sensors'], dict):
            for measurement, value in data['sensors'].items():
                try:
                    val_float = float(value)
                    sensor_obj = process_sensor_reading(device, measurement, val_float)

                    influx_action = "Skipped Influx"
                    if sensor_obj and sensor_obj.effective_data_type.startswith('INFLUX'):
                        if influx_source:
                            fields = {'value': val_float}
                            tags = {'device_id': device.device_id}
                            write_to_influx(influx_source, measurement, fields, tags)
                            influx_action = "Sent to Influx"
                        else:
                            influx_action = "Influx Not Configured"

                    if settings.WEBHOOK_SNIFFER:
                        message = f"WEBHOOK: Reading | Place: {place.name} | Device: {device.name} | Sensor: {measurement} | Value: {val_float} | Action: Stored Local, {influx_action}"
                        record_webhook_activity(message)

                except (ValueError, TypeError) as e:
                    logger.error(f"Could not process value '{value}' for measurement '{measurement}': {e}")
                except Exception as e:
                    logger.error(f"Failed to process data for device '{device_id}': {e}")

        return HttpResponse("POST request processed successfully")


@method_decorator(csrf_exempt, name='dispatch')
class SwitchBotWebhookReceiverView(View):
    """
    Handles incoming webhooks from SwitchBot.
    """
    def post(self, request: HttpRequest, place_slug: str) -> HttpResponse:
        try:
            place = Place.objects.get(slug=place_slug)
            influx_source = InfluxSource.objects.filter(place=place).first()
        except Place.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f"Place '{place_slug}' not found."}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON in request body.'}, status=400)

        context = data.get('context', {})
        device_id = context.get('deviceMac')

        if data.get('eventType') != 'changeReport' or not device_id:
            return JsonResponse({'status': 'ignored', 'message': 'Not a change report or no device MAC.'})

        try:
            device = Device.objects.get(device_id__iexact=device_id, location__place=place)
        except Device.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f"Device with ID '{device_id}' not found."}, status=404)

        status_map = {'temperature': 'temperature', 'humidity': 'humidity', 'battery': 'battery', 'lightLevel': 'light'}
        influx_fields = {}

        for key, measurement in status_map.items():
            if key in context:
                try:
                    value = float(context[key])
                    sensor_obj = process_sensor_reading(device, measurement, value)

                    influx_action = "Skipped Influx"
                    if sensor_obj and sensor_obj.effective_data_type.startswith('INFLUX'):
                        if influx_source:
                            influx_fields[measurement] = value
                            influx_action = "Queued for Influx"
                        else:
                            influx_action = "Influx Not Configured"

                    if settings.WEBHOOK_SNIFFER:
                        message = f"WEBHOOK: Reading | Place: {place.name} | Device: {device.name} | Sensor: {measurement} | Value: {value} | Action: Stored Local, {influx_action}"
                        record_webhook_activity(message)

                except (ValueError, TypeError):
                    logger.warning(f"Could not convert value '{context[key]}' for '{key}' to float.")

        if influx_fields and influx_source:
            try:
                tags = {'device_id': device.device_id, 'device_name': device.name}
                write_to_influx(influx_source, "switchbot_reading", influx_fields, tags)
            except Exception as e:
                logger.error(f"Failed to write SwitchBot data to InfluxDB for device '{device_id}': {e}")

        return JsonResponse({'status': 'success'})


@method_decorator(csrf_exempt, name='dispatch')
class ShellyWebhookReceiverView(View):
    """
    Handles incoming webhooks from Shelly devices.
    """
    def _process_readings(self, device, place, influx_source, params):
        influx_fields = {}
        key_map = {
            'apower': 'power', 'voltage': 'voltage', 'current': 'current',
            'temperature': 'temperature', 'temp': 'temperature', 'humidity': 'humidity',
            'pm2.5': 'pm25', 'pm25': 'pm25', 'battery': 'battery',
            'flood': 'flood', 'batV': 'battery_voltage'
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
                sensor_obj = process_sensor_reading(device, measurement_name, val_float)

                influx_action = "Skipped Influx"
                if sensor_obj and sensor_obj.effective_data_type.startswith('INFLUX'):
                    if influx_source:
                        influx_fields[measurement_name] = val_float
                        influx_action = "Queued for Influx"
                    else:
                        influx_action = "Influx Not Configured"

                if settings.WEBHOOK_SNIFFER:
                    message = f"WEBHOOK: Reading | Place: {place.name} | Device: {device.name} | Sensor: {measurement_name} | Value: {val_float} | Action: Stored Local, {influx_action}"
                    record_webhook_activity(message)
            else:
                logger.warning(f"Unknown Shelly sensor key '{key}' received from device '{device.name}'. Skipping.")

        if influx_fields and influx_source:
            try:
                tags = {'device_id': device.device_id, 'device_name': device.name}
                write_to_influx(influx_source, "shelly_reading", influx_fields, tags)
            except Exception as e:
                logger.error(f"Failed to write Shelly data to InfluxDB for device '{device.device_id}': {e}")

    def _get_device_or_create(self, place, device_id_str):
        """
        Helper to find a device by ID or suffix, or create it if not found.
        Parses Shelly IDs like 'shellyflood-FCF5C4B110A1' into Model='Flood', ID='FCF5C4B110A1'.
        """
        parsed_id = device_id_str
        model_name = None
        manufacturer = "Shelly"

        if '-' in device_id_str:
            parts = device_id_str.split('-')
            parsed_id = parts[-1]
            # Try to derive model from prefix (e.g. 'shellyflood' -> 'Flood')
            prefix = parts[0].lower()
            if 'flood' in prefix:
                model_name = "Flood"
            elif 'shelly1' in prefix:
                model_name = "1"
            elif 'plus' in prefix:
                model_name = "Plus"

        # Try to find device by exact match or by parsed ID
        device = Device.objects.filter(
            location__place=place,
            device_id__iexact=device_id_str
        ).first()

        if not device and parsed_id != device_id_str:
             device = Device.objects.filter(
                location__place=place,
                device_id__iexact=parsed_id
            ).first()

        if not device:
            # Auto-create device in Unassigned Devices
            unassigned_location = place.get_unassigned_location()

            # Format name as "Flood XXXXXX" (using last 6 chars of ID)
            display_id = parsed_id[-6:]
            device_name = f"{model_name or 'Device'} {display_id}".strip()

            device_type = None
            if model_name == "Flood":
                 device_type = DeviceType.objects.filter(name__iexact="Water Detector").first()

            device = Device.objects.create(
                device_id=parsed_id,  # Store the clean ID
                name=device_name,
                location=unassigned_location,
                manufacturer=manufacturer,
                model=model_name,
                device_type=device_type,
                is_active=False  # Unassigned devices must be inactive
            )
            if settings.WEBHOOK_SNIFFER:
                ic(f"WEBHOOK: Created new device | Place: {place.name} | Device: {device.name} | ID: {parsed_id}")

        return device

    def get(self, request: HttpRequest, place_slug: str, device_id: str = None) -> HttpResponse:
        try:
            place = Place.objects.get(slug=place_slug)
            influx_source = InfluxSource.objects.filter(place=place).first()
        except Place.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f"Place '{place_slug}' not found."}, status=404)

        data = request.GET

        if not device_id:
            device_id = data.get('id')
            if device_id and settings.WEBHOOK_SNIFFER:
                ic(f"WEBHOOK: Shelly Gen1 Request | Place: {place_slug} | Device: {device_id}")

        if not device_id:
            if not data:
                # Silently ignore empty requests (heartbeats/probes)
                return HttpResponse("No data received", status=200)

            if settings.WEBHOOK_SNIFFER:
                ic(f"WEBHOOK: Shelly Request Missing ID | Place: {place_slug} | Params: {data}")
            return JsonResponse({'status': 'error', 'message': 'No device identifier found in GET request.'}, status=400)

        device = self._get_device_or_create(place, device_id)
        self._process_readings(device, place, influx_source, data)
        return JsonResponse({'status': 'success'})

    def post(self, request: HttpRequest, place_slug: str, device_id: str = None) -> HttpResponse:
        try:
            place = Place.objects.get(slug=place_slug)
            influx_source = InfluxSource.objects.filter(place=place).first()
        except Place.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f"Place '{place_slug}' not found."}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)

        if not device_id:
            device_id = data.get('src') or data.get('device_id')
            if not device_id:
                device_info = data.get('device', {})
                device_id = device_info.get('mac') or device_info.get('id')

        if not device_id:
            return JsonResponse({'status': 'error', 'message': 'No device identifier found.'}, status=400)

        device = self._get_device_or_create(place, device_id)

        # If 'params' key exists, use it. Otherwise, assume data is at the root.
        params = data.get('params', data)
        self._process_readings(device, place, influx_source, params)

        return JsonResponse({'status': 'success'})
