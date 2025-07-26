import json
from django.http import HttpResponse, HttpRequest, JsonResponse
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

    def get(self, request: HttpRequest, place_slug: str, device_id: str = None) -> HttpResponse:
        """
        Handles GET requests from devices with query parameters.
        """
        ic("Webhook GET request received")
        ic(f"place_slug: {place_slug}")
        ic(f"device_id: {device_id}")

        if not device_id:
            ic("No device_id provided in GET request.")
            return JsonResponse({'status': 'error', 'message': 'Device ID is required for GET requests'}, status=400)

        query_params = request.GET.dict()
        ic("GET Query Parameters:", query_params)

        try:
            device = Device.objects.get(
                location__place__slug=place_slug,
                device_id__iexact=device_id
            )
            ic(f"Device found: {device}")
        except Device.DoesNotExist:
            ic(f"Device with id '{device_id}' in place '{place_slug}' not found.")
            return JsonResponse({'status': 'error', 'message': 'Device not found'}, status=404)

        ic(request.headers)
        
        for sensor_name, value in query_params.items():
            if sensor_name in self.IGNORED_KEYS:
                ic(f"Ignoring GET parameter: '{sensor_name}' with value '{value}'")
                continue
            
            ic(f"Processing GET parameter: sensor='{sensor_name}', value='{value}'")
            try:
                sensor, created = Sensor.objects.get_or_create(
                    device=device,
                    name__iexact=sensor_name,
                    defaults={
                        'name': sensor_name,
                        'sensor_type': 'OTHER',
                        'unit': 'NONE',
                        'data_type': 'DIRECT'
                    }
                )
                if created:
                    ic("CREATED new sensor", sensor)
                
                reading = SensorReading.objects.create(sensor=sensor, value=float(value))
                ic("Stored new reading", reading)

            except Exception as e:
                ic(f"ERROR processing sensor '{sensor_name}': {e}")
                return JsonResponse({'status': 'error', 'message': f'Error processing sensor {sensor_name}'}, status=500)

        return JsonResponse({'status': 'ok', 'message': 'Webhook received via GET', 'data': query_params})

    def post(self, request: HttpRequest, place_slug: str, device_id: str = None) -> HttpResponse:
        """
        Handles POST requests from devices.
        """
        ic("Webhook POST request received")
        ic(f"place_slug: {place_slug}")

        # Try to decode JSON payload first
        data = {}
        if request.body:
            try:
                if request.content_type == 'application/json':
                    data = json.loads(request.body)
                    ic("JSON Payload:", data)
                else:
                    ic("Request content-type is not application/json. Raw body:", request.body.decode('utf-8', errors='ignore'))
                    # Attempt to parse non-json as a simple key-value if needed, or handle as raw data
            except json.JSONDecodeError:
                ic("Failed to decode JSON body")
                ic(request.body.decode('utf-8', errors='ignore'))
                return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        
        # Determine the device identifier
        # Priority: URL -> JSON payload ('device_id', 'serial_number', 'mac')
        if not device_id:
            possible_id_keys = ['device_id', 'serial_number', 'mac']
            for key in possible_id_keys:
                if key in data:
                    device_id = data.get(key)
                    ic(f"Found device_id in payload: {device_id}")
                    break
        
        ic(f"device_id confirmed: {device_id}")
        
        device = None
        if device_id:
            try:
                device = Device.objects.get(
                    location__place__slug=place_slug,
                    device_id__iexact=device_id
                )
                ic("device found", device)
            except Device.DoesNotExist:
                ic("device not_found")
                # If device not found, create a new one in a default location
                try:
                    place = Place.objects.get(slug=place_slug)
                    unassigned_location = place.get_unassigned_location()
                    
                    # Create the new device
                    device = Device.objects.create(
                        name=f"New Device {device_id}",
                        device_id=device_id,
                        location=unassigned_location,
                        is_active=True,  # Or False, depending on desired behavior
                        model='Auto-created',
                        manufacturer='Unknown'
                    )
                    ic("Created new device", device)
                except Exception as e:
                    ic(f"Error creating new device or 'Unassigned' location: {e}")
                    return JsonResponse({'status': 'error', 'message': 'Failed to auto-create device'}, status=500)
        else:
            ic("No device_id in URL or payload. Logging payload and exiting.")
            return JsonResponse({'status': 'ok', 'message': 'Payload received without device_id, logged.'})

        # Process sensor readings for the identified device
        if device and data:
            # We can remove device_id from data so it's not processed as a sensor
            data.pop('device_id', None)
            data.pop('serial_number', None)
            data.pop('mac', None)
            for key in self.IGNORED_KEYS:
                data.pop(key, None)

            ic(f"Processing sensor values for device '{device.name}': {data}")
            for sensor_name, value in data.items():
                try:
                    sensor, created = Sensor.objects.get_or_create(
                        device=device,
                        name__iexact=sensor_name,
                        defaults={
                            'name': sensor_name,
                            'sensor_type': 'OTHER',  # Default type, can be updated later
                            'unit': 'NONE',
                            'data_type': 'DIRECT'
                        }
                    )
                    if created:
                        ic("CREATED new sensor", sensor)
                    
                    # Store the reading
                    reading = SensorReading.objects.create(sensor=sensor, value=float(value))
                    ic("Stored new reading", reading)

                except (ValueError, TypeError) as e:
                    ic(f"ERROR: Could not convert value '{value}' to float for sensor '{sensor_name}': {e}")
                except Exception as e:
                    ic(f"ERROR processing sensor '{sensor_name}': {e}")
        
        return JsonResponse({'status': 'ok', 'message': 'Webhook received'}) 