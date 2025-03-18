from django.urls import resolve
from django.contrib import messages
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from django.utils.deprecation import MiddlewareMixin

from .models import Place, ToastNotification

import json
from icecream import ic

class ToastMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ic("ToastMiddleware __call__:", {
        #     'path': request.path,
        #     'method': request.method,
        #     'is_ajax': request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        # })
        response = self.get_response(request)
        
        # Handle toast messages for any response type
        if hasattr(request, 'user') and request.user.is_authenticated:
            if 'toast_messages' in request.session:
                place_slug = getattr(request, 'place_slug', 'none')
                try:
                    place = Place.objects.get(slug=place_slug)
                except Place.DoesNotExist:
                    place = None

                for toast_data in request.session['toast_messages']:
                    notification = ToastNotification.objects.create(
                        user=request.user,
                        place=place,
                        message=toast_data['message'],
                        type=toast_data['type']
                    )
                
                # Clear the messages after processing
                del request.session['toast_messages']
                request.session.modified = True

        # Process response for toast messages
        return self.process_response(request, response)

    # resolved: ResolverMatch(func=sensors.views.location_views.LocationCreateView, args=(), kwargs={'place_slug': 'carpet'}, 
    #                         url_name='location_create', app_names=['sensors'], namespaces=['sensors'], route='<slug:place_slug>/location/create/',
    #                         captured_kwargs={'place_slug': 'carpet'})

    def process_response(self, request, response):
        # do not process static files or media files
        if any(path in request.path for path in ['/static/', '/media/']):
            return response
        
        # Get place_slug from URL - source of truth
        place_slug = None
        if hasattr(request, 'resolver_match') and request.resolver_match:
            place_slug = request.resolver_match.kwargs.get('place_slug', None)
        
        # DEBUG: Log request and session information
        ic("ToastMiddleware process_response", {
            'path': request.path,
            'method': request.method,
            'status_code': response.status_code,
            'place_slug': place_slug,
            'has_toast_message': hasattr(request, 'toast_message'),
            'session_keys': list(request.session.keys()) if hasattr(request, 'session') else None,
            'has_pending_toast': 'pending_toast' in request.session if hasattr(request, 'session') else False
        })
        
        # Add DIRECT data to the response if it's a redirect with toast
        if hasattr(request, 'toast_message') and response.status_code in [301, 302]:
            # Store toast directly in the session for guaranteed access
            if 'pending_toast' not in request.session:
                request.session['pending_toast'] = request.toast_message
                request.session.modified = True
                ic("Stored toast in pending_toast:", request.toast_message)
        
        # Initialize context data if using TemplateResponse
        context_data = {}
        if isinstance(response, TemplateResponse):
            # Ensure context_data exists and is a dictionary
            if hasattr(response, 'context_data') and response.context_data:
                context_data = response.context_data
            else:
                response.context_data = context_data
            
            # Add place_slug to context data
            context_data['place_slug'] = place_slug or 'none'
            
            # CHECK FOR PENDING TOAST ON EVERY TEMPLATE RESPONSE
            if hasattr(request, 'session') and 'pending_toast' in request.session:
                toast_data = request.session.pop('pending_toast')
                context_data['toast_message'] = toast_data
                request.session.modified = True
                ic("Added pending_toast to template context:", toast_data)
        
        place = None
        try:
            if place_slug:
                place = get_object_or_404(Place, slug=place_slug)
                # ic("place:", place)
                
                # Only add unread_count to TemplateResponse
                if isinstance(response, TemplateResponse):
                    user = request.user if hasattr(request, 'user') else None
                    if user and user.is_authenticated:
                        unread_count = ToastNotification.get_unread_count(
                            place=place,
                            user=user,
                        )
                        context_data['toast_unread_count'] = unread_count
        except Exception as e:
            # ic(f"Toast Middleware Error: {e}")
            pass

        try:
            # Check for request.toast_message
            if hasattr(request, 'toast_message'):
                toast_data = request.toast_message
                ic("Found toast_message in request:", toast_data)
                
                # Convert single toast to list if needed
                if not isinstance(toast_data, list):
                    toast_data = [toast_data]
                    
                # For redirect responses (302, 301), store toasts in session
                if response.status_code in [301, 302]:
                    # Initialize toast_messages as a list in session if it doesn't exist
                    if 'toast_messages' not in request.session:
                        request.session['toast_messages'] = []
                        
                    # Add all toast messages to the session list
                    request.session['toast_messages'].extend(toast_data)
                    request.session.modified = True
                    ic("Stored toast_messages in session for redirect:", request.session['toast_messages'])
                    
                # For TemplateResponse, add to the context
                elif isinstance(response, TemplateResponse):
                    # Initialize toast_messages as a list in context if it doesn't exist
                    if 'toast_messages' not in context_data:
                        context_data['toast_messages'] = []
                        
                    # Add all toast messages to the context list
                    context_data['toast_messages'].extend(toast_data)
                    ic("Added toast_messages to template context:", toast_data)

        except Exception as e:
            ic("Create toast notification error:", str(e))
            pass

        try:
            # Handle API responses - these already have toast data in JSON response
            if request.path.startswith('/api/'):
                return response

            # Handle GET with pending toast (after redirect)
            if request.method == 'GET' and isinstance(response, TemplateResponse):
                # Handle pending toast from session
                if 'toast_messages' in request.session:
                    ic("Processing toast_messages from session:", request.session['toast_messages'])
                    
                    # Initialize toast_messages in context if not present
                    if 'toast_messages' not in context_data:
                        context_data['toast_messages'] = []
                        
                    # Add session messages to context
                    pending_toasts = request.session.pop('toast_messages')
                    context_data['toast_messages'].extend(pending_toasts)
                    request.session.modified = True
                    ic("Added session toasts to template context:", pending_toasts)
                
                # Debug the final template context structure
                if hasattr(response, 'context_data') and response.context_data is not None:
                    ic("Final context_data keys:", list(response.context_data.keys()))
                    if response.context_data and 'toast_messages' in response.context_data:
                        ic("toast_messages in context:", response.context_data['toast_messages'])
                
        except Exception as e:
            ic("Error in process_response:", str(e))
            # Don't pass so we can see the error
        
        # DEBUGGING: Final check of context_data
        if isinstance(response, TemplateResponse):
            ic("Final context_data keys:", list(context_data.keys()))
            if 'toast_message' in context_data:
                ic("toast_message in final context:", context_data['toast_message'])
        
        return response

    def process_template_response(self, request, response):
        # Only handle template-specific operations here
        if isinstance(response, TemplateResponse) and not hasattr(response, 'context_data'):
            response.context_data = {}
        return response

class ToastDebugMiddleware(MiddlewareMixin):
    """Debug middleware to check if toast_message is present in the rendered HTML."""
    
    def process_response(self, request, response):
        # Only check HTML responses
        if hasattr(response, 'content') and b'<html' in response.content[:1000]:
            content = response.content.decode('utf-8')
            
            # Check if toast message is in the context
            has_toast_message = 'pending_toast' in request.session if hasattr(request, 'session') else False
            
            # Check if the toast container is in the HTML
            has_toast_container = 'id="toast-messages"' in content
            
            # Check if any server-toast-message is in the HTML
            has_server_toast = 'server-toast-message' in content
            
            # Log the results
            ic("ToastDebugMiddleware: Response check", {
                'path': request.path,
                'has_toast_message_in_session': has_toast_message,
                'has_toast_container_in_html': has_toast_container,
                'has_server_toast_in_html': has_server_toast,
            })
            
        return response