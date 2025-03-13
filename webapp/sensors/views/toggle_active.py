# from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin

from django.views import View

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
                'place': Place,
                'location': Location,
                'device': Device,
                'sensor': Sensor
            }

            model_class = model_map.get(model_type.lower())
            if not model_class:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid model type: {model_type}'
                }, status=400)

            # Get the object and validate ownership through place
            obj = get_object_or_404(model_class, pk=object_id)

            # Get the place based on model type
            if model_type == 'place':
                place = obj
            elif model_type == 'location':
                place = obj.place
            elif model_type == 'device':
                place = obj.location.place
            else:  # sensor
                place = obj.device.location.place

            # Verify place matches URL
            if place.slug != place_slug:
                return JsonResponse({
                    'success': False,
                    'error': 'Object does not belong to this place'
                }, status=403)

            # Toggle the active status
            obj.is_active = not obj.is_active
            obj.save()

            # Build success message
            if model_type == 'place':
                name_path = f"{obj.name}"
            elif model_type == 'location':
                name_path = f"{place.name} > {obj.name}"
            elif model_type == 'device':
                name_path = f"{place.name} > {obj.location.name} > {obj.name}"
            else:  # sensor
                name_path = f"{place.name} > {obj.device.location.name} > {obj.device.name} > {obj.name}"

            # Set toast message using our standard pattern
            request.toast_message = {
                'message': (
                    f"{'Activated' if obj.is_active else 'Deactivated'} {model_type}: "
                    f"<strong>{name_path}</strong>"
                ),
                'type': 'success' if obj.is_active else 'warning'
            }

            # Ensure the JSON response includes the toast data
            response_data = {
                'success': True,
                'is_active': obj.is_active,
                'toast': {
                    'message': request.toast_message['message'],
                    'type': request.toast_message['type']
                }
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
