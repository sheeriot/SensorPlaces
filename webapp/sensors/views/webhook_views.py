import json
from uuid import UUID
from django.http import HttpResponse, HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from icecream import ic

from sensors.models import Place, Device, Sensor, SensorReading, Location

@method_decorator(csrf_exempt, name='dispatch')
class WebhookReceiverView(View):
    """
    Handles incoming webhooks from devices.
    """
    IGNORED_KEYS = ['report_url']

    def get(self, request: HttpRequest, place_slug: str, uuid: UUID) -> HttpResponse:
        device_id = request.GET.get('device_id', None)
        query_params = request.GET.dict()
        
        # ic("Webhook GET request received")
        # ic(f"place_slug: {place_slug}")
        # ic(f"device_id: {device_id}")
        
        if not device_id:
            # ic("No device_id provided in GET request.")
            return HttpResponse("No device_id provided", status=400)
        
        # ic("GET Query Parameters:", query_params)
        
        try:
            device = Device.objects.get(device_id__iexact=device_id, location__place__slug=place_slug)
            # ic(f"Device found: {device}")
        except Device.DoesNotExist:
            # ic(f"Device with id '{device_id}' in place '{place_slug}' not found.")
            return HttpResponse(f"Device with id '{device_id}' not found.", status=404)
        
        # ic(request.headers)
        
        for sensor_name, value in query_params.items():
            if sensor_name in ['device_id']:
                # ic(f"Ignoring GET parameter: '{sensor_name}' with value '{value}'")
                continue
                
            # ic(f"Processing GET parameter: sensor='{sensor_name}', value='{value}'")
            
            try:
                # Get or create the sensor
                sensor, created = Sensor.objects.get_or_create(
                    device=device,
                    name=sensor_name,
                )
                
                if created:
                    # ic("CREATED new sensor", sensor)
                    pass
                
                # Store the new reading
                reading = SensorReading.objects.create(sensor=sensor, value=float(value))
                # ic("Stored new reading", reading)
                
            except Exception as e:
                # ic(f"ERROR processing sensor '{sensor_name}': {e}")
                return HttpResponse(f"Error processing sensor '{sensor_name}': {e}", status=400)

        return HttpResponse("GET request processed successfully")

    def post(self, request: HttpRequest, place_slug: str, uuid: UUID) -> HttpResponse:
        # ic("Webhook POST request received")
        # ic(f"place_slug: {place_slug}")

        device = None
        device_id = None
        data = None

        # Check content type and decode body
        if 'application/json' in request.content_type:
            try:
                data = json.loads(request.body)
                # ic("JSON Payload:", data)
            except json.JSONDecodeError:
                # ic("Failed to decode JSON body")
                # ic(request.body.decode('utf-8', errors='ignore'))
                return HttpResponse("Invalid JSON", status=400)
        else:
            # ic("Request content-type is not application/json. Raw body:", request.body.decode('utf-8', errors='ignore'))
            return HttpResponse("Content-Type must be application/json", status=400)
        
        # Determine device_id from URL parameter or JSON payload
        url_device_id = request.GET.get('device_id', None)
        payload_device_id = data.get('device_id', None) if isinstance(data, dict) else None
        
        if url_device_id:
            device_id = url_device_id
        elif payload_device_id:
            # ic(f"Found device_id in payload: {payload_device_id}")
            device_id = payload_device_id
        
        # ic(f"device_id confirmed: {device_id}")
        
        if device_id:
            try:
                device = Device.objects.get(
                    device_id__iexact=device_id,
                    location__place__slug=place_slug
                )
                # ic("device found", device)
            except Device.DoesNotExist:
                # ic("device not_found")
                # Create a new device in the 'Unassigned' location for the place.
                try:
                    place = Place.objects.get(slug=place_slug)
                    unassigned_location = place.get_unassigned_location()
                    device = Device.objects.create(
                        name=f"New Device - {device_id}",
                        device_id=device_id,
                        location=unassigned_location,
                        is_active=True
                    )
                    # ic("Created new device", device)
                except Exception as e:
                    # ic(f"Error creating new device or 'Unassigned' location: {e}")
                    return HttpResponse(f"Could not find or create device '{device_id}'.", status=400)
        else:
            # ic("No device_id in URL or payload. Logging payload and exiting.")
            # Log the payload for debugging purposes
            # logger.warning(f"Webhook received POST without device_id for place '{place_slug}': {data}")
            return HttpResponse("No device_id provided.", status=400)

        if isinstance(data, dict) and 'sensors' in data and isinstance(data['sensors'], dict):
            # ic(f"Processing sensor values for device '{device.name}': {data}")
            for sensor_name, value in data['sensors'].items():
                try:
                    sensor, created = Sensor.objects.get_or_create(
                        device=device,
                        name=sensor_name
                    )

                    if created:
                        # ic("CREATED new sensor", sensor)
                        pass

                    try:
                        reading = SensorReading.objects.create(sensor=sensor, value=float(value))
                        # ic("Stored new reading", reading)
                    except (ValueError, TypeError) as e:
                        # ic(f"ERROR: Could not convert value '{value}' to float for sensor '{sensor_name}': {e}")
                        pass
                except Exception as e:
                    # ic(f"ERROR processing sensor '{sensor_name}': {e}")
                    pass
        
        return HttpResponse("POST request processed successfully") 