# from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.db.models import Count, Q
from django.utils.safestring import mark_safe
from icecream import ic

from ..models import Place, Location, Device, Sensor
from .device_views import DeviceUpdateView
from .location_views import LocationUpdateView
from .sensor_views import SensorUpdateView


@method_decorator(csrf_protect, name='dispatch')
class ToggleActiveView(LoginRequiredMixin, View):
    def post(self, request, place_slug):
        try:
            data = json.loads(request.body)
            model_type = data.get('model_type')
            object_id = data.get('id')

            if not model_type or not object_id:
                return JsonResponse({
                    'success': False,
                    'error': 'model_type and id are required'
                }, status=400)

            # Map model types to actual models
            model_map = {
                'device': Device,
                'sensor': Sensor
            }

            # Prevent toggling Place objects as required
            if model_type.lower() == 'place':
                return JsonResponse({
                    'success': False,
                    'error': 'Toggling places is not allowed'
                }, status=400)

            model_class = model_map.get(model_type.lower())
            if not model_class:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid model type: {model_type}'
                }, status=400)

            # Get the object and validate ownership through place
            obj = get_object_or_404(model_class, pk=object_id)

            # Get the place based on model type
            if model_type == 'device':
                place = obj.location.place
                dependencies = self._get_device_dependencies(obj)
            else:  # sensor
                place = obj.device.location.place
                dependencies = []  # Sensors don't have dependencies

            # Verify place matches URL
            if place.slug != place_slug:
                return JsonResponse({
                    'success': False,
                    'error': 'Object does not belong to this place'
                }, status=403)

            # Toggle the active status
            was_active = obj.is_active
            obj.is_active = not obj.is_active
            obj.save()

            # If we're deactivating, also deactivate all dependent items
            deactivated_items = []
            if was_active and not obj.is_active:
                deactivated_items = self._deactivate_dependencies(model_type, obj)

            # If we didn't deactivate items but have dependencies, use those for the response
            if not deactivated_items and dependencies and not obj.is_active:
                deactivated_items = dependencies

            # Get the appropriate help text based on model type
            help_text = None
            if model_type == 'device':
                help_text = self._get_device_help_text(obj)
            elif model_type == 'sensor':
                help_text = self._get_sensor_help_text(obj)

            # Build the toast message
            toast_message = self._build_toast_message(model_type, obj, place, was_active, deactivated_items, help_text)

            # Set toast message using our standard pattern
            request.toast_message = toast_message

            # Ensure the JSON response includes the toast data
            response_data = {
                'success': True,
                'new_state': obj.is_active,
                'dependencies': deactivated_items,
                'toast': toast_message
            }

            return JsonResponse(response_data)

        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    def _build_toast_message(self, model_type, obj, place, was_active, deactivated_items, help_text=None):
        """Build a standard toast message for toggle operations"""
        # Build basic path info based on model type
        if model_type == 'device':
            name_path = f"{place.name} > {obj.location.name} > {obj.name}"
        else:  # sensor
            name_path = f"{place.name} > {obj.device.location.name} > {obj.device.name} > {obj.name}"

        # Build dependency message if deactivating
        dependency_info = ""
        if was_active and not obj.is_active and deactivated_items:
            dependency_info = "<br><small class='text-warning'><i class='bi bi-exclamation-triangle me-1'></i>"
            dependency_info += f"Also deactivated {len(deactivated_items)} dependent item(s):</small>"
            dependency_info += "<ul class='mb-0 mt-1 small'>"
            for dep in deactivated_items[:5]:  # Limit to showing 5 dependencies
                dependency_info += f"<li>{dep['name']}</li>"
            if len(deactivated_items) > 5:
                dependency_info += f"<li>... and {len(deactivated_items) - 5} more</li>"
            dependency_info += "</ul>"

        # Build the full message
        message = (
            f"{'Activated' if obj.is_active else 'Deactivated'} {model_type}: "
            f"<strong>{name_path}</strong>{dependency_info}"
        )

        # Add help text if provided and object is inactive
        if help_text and not obj.is_active:
            message += f"<br><small class='text-warning'>{help_text}</small>"

        return {
            'message': message,
            'type': 'success' if obj.is_active else 'warning'
        }

    def _get_device_help_text(self, device):
        """Get help text for device inactivation from DeviceUpdateView"""
        try:
            # Create a dummy instance to get the help text
            view = DeviceUpdateView()
            help_text, _ = view.get_device_inactive_help_text(device)
            # Log if the help text contains a wrapper
            # ic("Device help text contains wrapper:", help_text)
            return help_text
        except Exception as e:
            return None

    def _get_sensor_help_text(self, sensor):
        """Get help text for sensor inactivation from SensorUpdateView"""
        try:
            # Create a dummy instance to get the help text
            view = SensorUpdateView()
            help_text = view.get_sensor_inactive_help_text(sensor)
            # Log if the help text contains a wrapper
            # ic("Sensor help text contains wrapper:", help_text)
            return help_text
        except Exception as e:
            return None

    def _deactivate_dependencies(self, model_type, obj):
        """Deactivate dependent items and return information about them"""
        deactivated = []

        if model_type == 'device':
            # Deactivate all sensors in this device
            sensors = Sensor.objects.filter(device=obj, is_active=True)
            for sensor in sensors:
                sensor.is_active = False
                sensor.save()
                deactivated.append({
                    'id': sensor.id,
                    'name': sensor.name,
                    'type': 'sensor'
                })

        return deactivated

    def _get_device_dependencies(self, device):
        """Get active sensors that will be affected by device toggle"""
        active_sensors = Sensor.objects.filter(
            device=device,
            is_active=True
        ).values('id', 'name')

        dependencies = []
        for sensor in active_sensors:
            dependencies.append({
                'id': sensor['id'],
                'name': sensor['name'],
                'type': 'sensor'
            })

        return dependencies
