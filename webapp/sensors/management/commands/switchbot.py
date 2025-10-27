import time, uuid, hmac, base64, json
import requests
from hashlib import sha256

from django.core.management.base import BaseCommand
from django.conf import settings

from sensors.models import Device, DeviceType, Place, Location, Sensor, SensorType, Unit
from sensors.switchbot_client import list_devices, get_status

# --- Helper functions from your script ---

# BASE = "https://api.switch-bot.com"

# def _headers():
#     """Builds the required authentication headers for the SwitchBot API."""
#     token = getattr(settings, 'SWITCHBOT_TOKEN', None)
#     secret = getattr(settings, 'SWITCHBOT_SECRET', None)

#     if not token or not secret:
#         raise Exception(
#             "SWITCHBOT_TOKEN and SWITCHBOT_SECRET must be configured in your Django settings and cannot be empty. "
#             "Please check your environment variables (e.g., env/django.env)."
#         )

#     t = str(int(time.time() * 1000))
#     nonce = str(uuid.uuid4())
#     data = f"{token}{t}{nonce}".encode("utf-8")
#     secret_bytes = secret.encode("utf-8")
#     sign = base64.b64encode(hmac.new(secret_bytes, msg=data, digestmod=sha256).digest()).decode("utf-8")
    
#     return {
#         "Authorization": token,
#         "Content-Type": "application/json; charset=utf8",
#         "t": t,
#         "sign": sign,
#         "nonce": nonce,
#     }

# def list_devices():
#     """Fetches a list of all devices from the SwitchBot API."""
#     r = requests.get(f"{BASE}/v1.1/devices", headers=_headers(), timeout=15)
#     r.raise_for_status()
#     return r.json()

# def get_status(device_id: str):
#     """Fetches the status of a specific device from the SwitchBot API."""
#     r = requests.get(f"{BASE}/v1.1/devices/{device_id}/status", headers=_headers(), timeout=15)
#     r.raise_for_status()
#     return r.json()

# --- Management Command ---

class Command(BaseCommand):
    help = 'Interacts with the SwitchBot API to list devices or get device status.'

    def add_arguments(self, parser):
        # Create a subcommand parser
        subparsers = parser.add_subparsers(dest='command', required=True, help='Sub-command help')

        # Subcommand for "list"
        subparsers.add_parser('list', help='List all SwitchBot devices.')

        # Subcommand for "status"
        parser_status = subparsers.add_parser('status', help='Get the status of a specific device.')
        parser_status.add_argument('device_id', type=str, help='The ID of the device to get status for.')

        # Subcommand for "inspect"
        parser_inspect = subparsers.add_parser('inspect', help='Get the raw cloud data for a specific SwitchBot device.')
        parser_inspect.add_argument('device_id', type=str, help='The device ID to inspect.')

        # Subcommand for "sync"
        parser_sync = subparsers.add_parser('sync', help='Sync SwitchBot devices with the database.')
        parser_sync.add_argument('--place', type=str, required=True, help='The slug of the Place to perform the sync against.')

    def handle(self, *args, **options):
        command = options['command']

        try:
            if command == 'list':
                self.stdout.write("Fetching device list from SwitchBot API...")
                devices = list_devices()
                self.stdout.write(json.dumps(devices, indent=2))

            elif command == 'status':
                device_id = options['device_id']
                self.stdout.write(f"Fetching status for device {device_id}...")
                status = get_status(device_id)
                self.stdout.write(json.dumps(status, indent=2))
            
            elif command == 'inspect':
                device_id = options['device_id']
                self.stdout.write(f"Inspecting cloud data for device {device_id}...")
                try:
                    status = get_status(device_id)
                    self.stdout.write(json.dumps(status, indent=2))
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 404:
                        self.stderr.write(self.style.ERROR(f"Device with ID '{device_id}' not found in SwitchBot cloud."))
                    else:
                        self.stderr.write(self.style.ERROR(f"API request failed: {e}"))

            elif command == 'sync':
                self.sync_devices(options)

        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"API request failed: {e}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"An unexpected error occurred: {e}"))

    def _create_device(self, device_item, location, sensor_types):
        """Helper function to create a single device, returns 1 if created, 0 otherwise."""
        device_id = device_item['deviceId']
        
        device, created = Device.objects.get_or_create(
            device_id=device_id,
            defaults={
                'name': device_item['deviceName'],
                'model': device_item.get('deviceType', 'Unknown'),
                'manufacturer': 'SwitchBot',
                'is_switchbot': True,
                'switchbot_hub_device_id': device_item.get('hubDeviceId'),
                'location': location,
                'is_active': not location.slug == 'unassigned-devices'
            }
        )

        if created:
            api_device_type_str = device.model
            
            if 'Hub' in api_device_type_str:
                device_type_name = "SwitchBot Hub"
            else:
                device_type_name = api_device_type_str

            device_type, _ = DeviceType.objects.get_or_create(
                name=device_type_name,
                defaults={'description': f'A {device_type_name} from SwitchBot.'}
            )
            device.device_type = device_type
            device.save()
            self.stdout.write(self.style.SUCCESS(f"Imported new device: {device.name} ({device_id})"))
        
        # Auto-create sensors for meter devices
        api_device_type_str = device.model
        meter_types = ["Meter", "Meter Plus", "Outdoor Meter", "Meter Pro", "WoSensorTH"]
        if any(meter_type in api_device_type_str for meter_type in meter_types):
            
            s1, s1_created = Sensor.objects.get_or_create(
                device=device,
                sensor_type=sensor_types['temperature'],
                defaults={'name': f'{device.name} Temperature'}
            )
            s2, s2_created = Sensor.objects.get_or_create(
                device=device,
                sensor_type=sensor_types['humidity'],
                defaults={'name': f'{device.name} Humidity'}
            )
            s3, s3_created = Sensor.objects.get_or_create(
                device=device,
                sensor_type=sensor_types['battery'],
                defaults={'name': f'{device.name} Battery'}
            )

            if created or any([s1_created, s2_created, s3_created]):
                 self.stdout.write(self.style.SUCCESS(f"    - Ensured Temperature, Humidity, and Battery sensors for {device.name}."))

        return 1 if created else 0

    def sync_devices(self, options):
        place_slug = options['place']
        try:
            place = Place.objects.get(slug=place_slug)
        except Place.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Place with slug '{place_slug}' not found."))
            return

        self.stdout.write(f"Starting SwitchBot sync for place: {place.name}")

        try:
            api_devices_body = list_devices()['body']
            all_api_devices = api_devices_body.get('deviceList', [])
            all_api_infrared_devices = api_devices_body.get('infraredRemoteList', [])
            all_api_devices.extend(all_api_infrared_devices)
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"API request failed: {e}"))
            return
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"An error occurred while fetching devices from SwitchBot API: {e}"))
            return

        existing_devices = Device.objects.filter(is_switchbot=True).select_related('location__place')
        existing_device_ids = {d.device_id: d for d in existing_devices if d.device_id}

        all_devices_with_status = []
        new_devices_to_import = []
        importable_idx = 1

        # Process all devices from the API
        for device in all_api_devices:
            device_id = device['deviceId']
            device_name = device['deviceName']
            device_type = device.get('deviceType', 'Infrared Remote')

            if device_id in existing_device_ids:
                existing_device = existing_device_ids[device_id]
                status = f"Existing in '{existing_device.location.place.name}'"
                all_devices_with_status.append({
                    'name': device_name,
                    'type': device_type,
                    'id': device_id,
                    'status': status,
                    'is_new': False,
                    'import_idx': ''
                })
            else:
                new_devices_to_import.append(device)
                status = "New"
                all_devices_with_status.append({
                    'name': device_name,
                    'type': device_type,
                    'id': device_id,
                    'status': status,
                    'is_new': True,
                    'import_idx': f"[{importable_idx}]"
                })
                importable_idx += 1

        # Sort devices to show existing ones first
        all_devices_with_status.sort(key=lambda x: x['is_new'])

        self.stdout.write("\n--- SwitchBot Cloud Device Summary ---")
        header = f"{'[#]':<4} {'Device Name':<25} {'Type':<20} {'Device ID':<20} {'Status'}"
        self.stdout.write(self.style.SUCCESS(header))
        self.stdout.write("-" * (len(header) + 5)) # A bit of padding

        for dev_info in all_devices_with_status:
            idx_str = dev_info['import_idx']
            status_str = dev_info['status']
            
            if dev_info['is_new']:
                status_str = self.style.WARNING(status_str)

            self.stdout.write(
                f"{idx_str:<4} {dev_info['name']:<25} {dev_info['type']:<20} {dev_info['id']:<20} {status_str}"
            )

        if not new_devices_to_import:
            self.stdout.write(self.style.SUCCESS("\nAll devices are in sync. Nothing to import."))
            return
        
        self.stdout.write("\n  [0] Quit")
        choice_str = input(f"Enter number(s) to import into '{place.name}' (e.g. '1 3' or 'all'), or 0 to quit: ").lower().strip()

        if not choice_str or choice_str in ['0', 'q']:
            self.stdout.write("Sync cancelled.")
            return

        # Ensure essential SensorTypes and Units exist
        celsius_unit, _ = Unit.objects.get_or_create(name="Celsius", defaults={'symbol': '°C'})
        percent_rh_unit, _ = Unit.objects.get_or_create(name="Relative Humidity", defaults={'symbol': '%RH'})
        percent_unit, _ = Unit.objects.get_or_create(name="Percent", defaults={'symbol': '%'})

        sensor_types = {
            'temperature': SensorType.objects.get_or_create(name="Temperature", defaults={'default_unit': celsius_unit})[0],
            'humidity': SensorType.objects.get_or_create(name="Humidity", defaults={'default_unit': percent_rh_unit})[0],
            'battery': SensorType.objects.get_or_create(name="Battery", defaults={'default_unit': percent_unit})[0]
        }
        
        unassigned_location = place.get_unassigned_location()
        created_total = 0

        indices_to_import = []
        if choice_str == 'all':
            indices_to_import = range(len(new_devices_to_import))
        else:
            try:
                choices = [int(c.strip()) - 1 for c in choice_str.replace(',', ' ').split() if c.strip().isdigit()]
                indices_to_import = [i for i in choices if 0 <= i < len(new_devices_to_import)]
            except ValueError:
                self.stderr.write(self.style.ERROR("Invalid input. Please enter numbers, 'all', or '0'."))
                return
        
        for index in indices_to_import:
            device_to_import = new_devices_to_import[index]
            created_total += self._create_device(device_to_import, unassigned_location, sensor_types)

        self.stdout.write(self.style.SUCCESS(f"\nSync complete. {created_total} new device(s) imported into '{place.name}'."))
