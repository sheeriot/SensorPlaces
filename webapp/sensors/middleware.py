from icecream import ic
from .models import ToastNotification, Place
from django.urls import resolve
from django.contrib import messages
import json
from django.template.response import TemplateResponse

class ToastMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ic("ToastMiddleware __call__:", {
            'path': request.path,
            'method': request.method,
            'is_ajax': request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        })
        response = self.get_response(request)
        return self.process_response(request, response)

    def process_response(self, request, response):
        if any(path in request.path for path in ['/static/', '/media/']):
            return response

        try:
            resolved = resolve(request.path)
            place_slug = resolved.kwargs.get('place_slug')

            # Log initial state
            ic("ToastMiddleware process_response:", {
                'path': request.path,
                'method': request.method,
                'status_code': response.status_code,
                'has_toast_message': hasattr(request, 'toast_message'),
                'place_slug': place_slug
            })

            if request.user.is_authenticated and place_slug:
                place = Place.objects.get(slug=place_slug)

                # Handle POST with redirect (form submissions)
                if (request.method == 'POST' and 
                    hasattr(request, 'toast_message') and 
                    response.status_code == 302):
                    
                    ic("Processing POST redirect with toast:", {
                        'message': request.toast_message.get('message'),
                        'type': request.toast_message.get('type')
                    })
                    
                    # Create notification in database first
                    notification = ToastNotification.objects.create(
                        user=request.user,
                        place=place,
                        message=request.toast_message['message'],
                        type=request.toast_message['type']
                    )
                    ic("Created notification:", {
                        'id': notification.id,
                        'message': notification.message[:50] + '...' if len(notification.message) > 50 else notification.message
                    })
                    
                    # Then store in session for redirect
                    request.session['pending_toast'] = request.toast_message
                    ic("Stored toast in session:", request.toast_message)

                # Handle GET with pending toast (after redirect)
                elif request.method == 'GET' and isinstance(response, TemplateResponse):
                    # Update unread count
                    unread_count = ToastNotification.get_unread_count(
                        user=request.user,
                        place=place
                    )
                    response.context_data['toast_unread_count'] = unread_count
                    ic("Updated unread count:", unread_count)

                    # Process pending toast
                    if 'pending_toast' in request.session:
                        toast_data = request.session.pop('pending_toast')
                        ic("Processing pending toast from session:", toast_data)
                        
                        # Add to messages
                        messages.add_message(request, messages.INFO, json.dumps(toast_data))
                        ic("Added message to request:", {
                            'toast_data': toast_data,
                            'message_count': len(list(messages.get_messages(request)))
                        })

        except Exception as e:
            ic("Middleware error:", {
                'error': str(e),
                'path': request.path,
                'method': request.method
            })
        
        return response

    def process_template_response(self, request, response):
        if request.path.startswith('/api/') or any(path in request.path for path in ['/static/', '/media/']):
            return response

        if hasattr(response, 'context_data') and request.user.is_authenticated:
            try:
                # Get place_slug from URL kwargs
                resolved = resolve(request.path)
                place_slug = resolved.kwargs.get('place_slug')
                
                ic("Processing template response:", {
                    'path': request.path,
                    'place_slug': place_slug,
                    'has_context_data': bool(response.context_data),
                    'has_pending_toast': 'pending_toast' in request.session
                })
                
                # Get unread count - only if we have a place
                if place_slug:
                    place = Place.objects.get(slug=place_slug)
                    unread_count = ToastNotification.get_unread_count(
                        user=request.user,
                        place=place
                    )
                    response.context_data['toast_unread_count'] = unread_count
                    ic("Updated unread count for place:", {
                        'place': place.name,
                        'unread_count': unread_count
                    })
                
                # If there's a pending toast, add it to template context
                if 'pending_toast' in request.session:
                    toast_data = request.session.pop('pending_toast')
                    ic("Processing pending toast in template:", toast_data)
                    
                    # Add to template context instead of messages
                    response.context_data['toast_message'] = toast_data
                    ic("Added toast to template context:", {
                        'toast_data': toast_data,
                        'context_keys': list(response.context_data.keys())
                    })
                
                ic("Template response context complete:", {
                    'has_messages': bool(list(messages.get_messages(request))),
                    'context_keys': list(response.context_data.keys())
                })
                
            except Exception as e:
                ic("Template response error:", {
                    'error': str(e),
                    'path': request.path
                })
        
        return response