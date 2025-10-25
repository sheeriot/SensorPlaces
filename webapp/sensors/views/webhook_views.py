import json
from uuid import UUID
import logging
from django.http import HttpResponse, HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from icecream import ic

from sensors.models import Place, Device, Sensor, SensorReading, Location, InfluxSource, SensorType
from ..influx_client import write_to_influx

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class WebhookReceiverView(View):
    """
    Handles incoming webhooks from generic devices and writes to InfluxDB.
    """

    def post(self, request: HttpRequest, place_slug: str, uuid: UUID) -> HttpResponse:
        try:
            place = Place.objects.get(slug=place_slug)
            influx_source = InfluxSource.objects.filter(place=place).first()
            if not influx_source:
                logger.error(f"No InfluxSource found for place '{place_slug}'")
                return HttpResponse("InfluxDB source not configured for this place.", status=500)
        except Place.DoesNotExist:
            return HttpResponse(f"Place '{place_slug}' not found.", status=404)
        except Exception as e:
            logger.error(f"Error getting InfluxSource for place '{place_slug}': {e}")
            return HttpResponse("Server configuration error.", status=500)

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
            # Optionally create a new device if it doesn't exist
            # For now, we will just return an error
            logger.warning(f"Device with ID '{device_id}' not found in place '{place_slug}'.")
            return HttpResponse(f"Device '{device_id}' not found.", status=404)

        if 'sensors' in data and isinstance(data['sensors'], dict):
            for measurement, value in data['sensors'].items():
                try:
                    # LoRaWAN devices often send float values directly
                    fields = {'value': float(value)}
                    tags = {'device_id': device.device_id}
                    write_to_influx(influx_source, measurement, fields, tags)
                except (ValueError, TypeError) as e:
                    logger.error(f"Could not process value '{value}' for measurement '{measurement}': {e}")
                except Exception as e:
                    logger.error(f"Failed to write to InfluxDB for device '{device_id}': {e}")

        return HttpResponse("POST request processed successfully")


@method_decorator(csrf_exempt, name='dispatch')
class SwitchBotWebhookReceiverView(View):
    """
    Handles incoming webhooks from SwitchBot and writes to InfluxDB.
    """
    def post(self, request: HttpRequest, place_slug: str) -> HttpResponse:
        try:
            place = Place.objects.get(slug=place_slug)
            influx_source = InfluxSource.objects.filter(place=place).first()
            if not influx_source:
                logger.error(f"No InfluxSource found for place '{place_slug}'")
                return JsonResponse({'status': 'error', 'message': 'InfluxDB not configured for this place.'}, status=500)
        except Place.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f"Place '{place_slug}' not found."}, status=404)

        try:
            data = json.loads(request.body)
            # Log the full webhook body for debugging
            logger.debug(f"SwitchBot webhook received for '{place.name}': {json.dumps(data)}")
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON in request body.'}, status=400)

        event_type = data.get('eventType')
        context = data.get('context', {})
        device_id = context.get('deviceMac')

        if event_type != 'changeReport' or not device_id:
            return JsonResponse({'status': 'ignored', 'message': 'Not a change report or no device MAC.'})

        try:
            device = Device.objects.get(device_id__iexact=device_id, location__place=place)
        except Device.DoesNotExist:
            logger.warning(f"Received SwitchBot webhook for unknown device_id '{device_id}' in place '{place.name}'")
            return JsonResponse({'status': 'error', 'message': f"Device with ID '{device_id}' not found."}, status=404)

        # Mapping of SwitchBot context keys to our measurements/fields
        status_map = {
            'temperature': 'temperature',
            'humidity': 'humidity',
            'battery': 'battery'
        }

        fields_to_write = {}
        for key, measurement in status_map.items():
            if key in context:
                try:
                    value = float(context[key])
                    fields_to_write[measurement] = value
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert value '{context[key]}' for '{key}' to float.")
        
        if fields_to_write:
            try:
                # For SwitchBot, we can use a generic measurement name like 'sensor_reading'
                # and put the specific type in a field.
                # Or, we can create separate measurements. Let's write them as separate fields in one measurement.
                tags = {'device_id': device.device_id, 'device_name': device.name}
                write_to_influx(influx_source, "switchbot_reading", fields_to_write, tags)
                
            except Exception as e:
                logger.error(f"Failed to write SwitchBot data to InfluxDB for device '{device_id}': {e}")
                return JsonResponse({'status': 'error', 'message': 'Failed to write to database.'}, status=500)

        return JsonResponse({'status': 'success'}) 