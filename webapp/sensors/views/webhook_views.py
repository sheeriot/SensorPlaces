import json
from uuid import UUID
import logging
from django.conf import settings
from django.http import HttpResponse, HttpRequest, JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from sensors.models import Place, Device, InfluxStore
from sensors.services.sensor_service import process_sensor_reading
from sensors.services.shelly_service import ShellyService
from sensors.services.switchbot_service import SwitchBotService, KEY_MAP
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
            # The service will handle its own InfluxStore logic.
            # Do not pass influx_store here.
            shelly_service = ShellyService(place=place)
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
                    # The service will handle storage, including InfluxDB.
                    sensor_obj = process_sensor_reading(device, measurement, val_float)

                    influx_action = "Skipped"
                    # Log based on what the service likely did.
                    if sensor_obj and sensor_obj.data_type.startswith('INFLUX'):
                            influx_action = "Sent to Influx"
                    elif not place.default_influx_store:
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
            # Initialize the SwitchBotService with the place.
            # The service will determine which InfluxStore to use (default or SwitchBot-specific).
            switchbot_service = SwitchBotService(place=place)
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
                    # The service now handles its own InfluxStore, so we don't pass it here.
                    sensor_obj = process_sensor_reading(device, measurement, value)

                    influx_action = "Skipped Influx"
                    if sensor_obj and sensor_obj.data_type.startswith('INFLUX'):
                        # The service's write method will handle the logic, so we just queue the fields.
                            influx_fields[measurement] = value
                            influx_action = "Queued for Influx"

                    if settings.WEBHOOK_SNIFFER:
                        message = f"WEBHOOK: Reading | Place: {place.name} | Device: {device.name} | Sensor: {measurement} | Value: {value} | Action: Stored Local, {influx_action}"
                        record_webhook_activity(message)

                except (ValueError, TypeError):
                    logger.warning(f"Could not convert value '{context[key]}' for '{key}' to float.")

        if influx_fields:
            try:
                # Let the service handle the writing. It already knows the correct store.
                switchbot_service.write_webhook_data(device, influx_fields)
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

        # The device_id from the URL has priority, but the service will still need the one from the payload.
        if not device_id:
            device_id = data.get('id')

        # Initialize the ShellyService.
        shelly_service = ShellyService(place=place)
        try:
            shelly_service.process_data(device_id, data, request)
        except ValueError as e:
            # This will catch the case where no ID is found at all.
            if settings.WEBHOOK_SNIFFER:
                from icecream import ic
                ic(f"WEBHOOK: Shelly Request Missing ID | Place: {place_slug} | Params: {data}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

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

        # Initialize the ShellyService.
        shelly_service = ShellyService(place=place)
        try:
            shelly_service.process_data(device_id, params, request)
        except ValueError as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

        return JsonResponse({'status': 'success'})
