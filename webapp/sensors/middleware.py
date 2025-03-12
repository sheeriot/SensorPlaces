from icecream import ic
from .models import ToastNotification, Place
from django.db.models import Count
from django.urls import resolve
from django.contrib import messages

class ToastMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not any(path in request.path for path in ['/static/', '/media/']):
            try:
                resolved = resolve(request.path)
                place_slug = resolved.kwargs.get('place_slug')
                
                # Handle toast_message from views
                if hasattr(request, 'toast_message') and request.user.is_authenticated:
                    ic("Processing toast message:", request.toast_message)
                    
                    # Get place from URL
                    if place_slug:
                        place = Place.objects.get(slug=place_slug)
                        
                        # Create ToastNotification for all messages
                        ToastNotification.objects.create(
                            user=request.user,
                            place=place,
                            message=request.toast_message['message'],
                            type=request.toast_message['type']
                        )
                        
                        # Add to Django messages for immediate display
                        messages.add_message(
                            request,
                            messages.INFO,  # Level doesn't matter as we use our own type
                            request.toast_message
                        )
                    
            except Exception as e:
                ic("Middleware error:", str(e))
        
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
                response.context_data['toast_unread_count'] = unread_count
                
                # Debug output
                ic("Template response context:", {
                    'unread_count': unread_count,
                    'place_slug': place_slug,
                    'has_messages': bool(list(messages.get_messages(request)))
                })
                
            except Exception as e:
                ic("Template response error:", str(e))
        
        return response