from icecream import ic
from .models import ToastNotification, Place
from django.db.models import Count
from django.urls import resolve

class ToastMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not any(path in request.path for path in ['/static/', '/media/']):
            # Get place_slug from URL kwargs
            try:
                resolved = resolve(request.path)
                place_slug = resolved.kwargs.get('place_slug')
                
                if hasattr(request, 'toast_message') and request.user.is_authenticated:
                    # Store the place with the toast message
                    if place_slug:
                        place = Place.objects.get(slug=place_slug)
                        request.toast_message['place'] = place
                    ic("Found toast message with place", request.toast_message)
            except:
                pass
        
        response = self.get_response(request)
        return response

    def process_template_response(self, request, response):
        if request.path.startswith('/api/') or any(path in request.path for path in ['/static/', '/media/']):
            return response

        if hasattr(response, 'context_data') and request.user.is_authenticated:
            try:
                # Get place_slug from URL kwargs
                resolved = resolve(request.path)
                place_slug = resolved.kwargs.get('place_slug')
                
                # Get unread count
                if place_slug:
                    place = Place.objects.get(slug=place_slug)
                    unread_count = ToastNotification.get_unread_count(
                        user=request.user,
                        place=place
                    )
                    response.context_data['current_place'] = place
                else:
                    unread_count = ToastNotification.get_unread_count(
                        user=request.user
                    )
                
                # Update context
                if 'body_data_attributes' not in response.context_data:
                    response.context_data['body_data_attributes'] = {}
                
                response.context_data['body_data_attributes'].update({
                    'toast-unread-count': str(unread_count)
                })
                response.context_data['toast_unread_count'] = unread_count
                
            except Exception as e:
                ic("Error in toast middleware:", str(e))
        
        return response