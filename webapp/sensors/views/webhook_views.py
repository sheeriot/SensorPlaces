import json
from uuid import UUID
import logging
from django.conf import settings
from django.http import HttpResponse, HttpRequest, JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from sensors.models import Place, Device, InfluxSource
from ..influx_client import write_to_influx
from sensors.services.sensor_service import process_sensor_reading
from sensors.services.shelly_service import ShellyService
from sensors.utils import record_webhook_activity

logger = logging.getLogger(__name__)

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
    def get(self, request: HttpRequest, place_slug: str, device_id: str = None) -> HttpResponse:
        try:
            place = Place.objects.get(slug=place_slug)
        except Place.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f"Place '{place_slug}' not found."}, status=404)

        data = request.GET

        if not device_id:
            device_id = data.get('id')
            if device_id and settings.WEBHOOK_SNIFFER:
                from icecream import ic
                ic(f"WEBHOOK: Shelly Gen1 Request | Place: {place_slug} | Device: {device_id}")

        if not device_id:
            if not data:
                # Silently ignore empty requests (heartbeats/probes)
                return HttpResponse("No data received", status=200)

            if settings.WEBHOOK_SNIFFER:
                from icecream import ic
                ic(f"WEBHOOK: Shelly Request Missing ID | Place: {place_slug} | Params: {data}")
            return JsonResponse({'status': 'error', 'message': 'No device identifier found in GET request.'}, status=400)

        service = ShellyService(place)
        service.process_data(device_id, data)
        return JsonResponse({'status': 'success'})

    def post(self, request: HttpRequest, place_slug: str, device_id: str = None) -> HttpResponse:
        try:
            place = Place.objects.get(slug=place_slug)
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

        # If 'params' key exists, use it. Otherwise, assume data is at the root.
        params = data.get('params', data)

        service = ShellyService(place)
        service.process_data(device_id, params)

        return JsonResponse({'status': 'success'})
