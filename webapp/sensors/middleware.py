from django.urls import resolve
from django.contrib import messages
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404

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
            # ic('is template response', place_slug)

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

        toast_data = None
        try:
            # Check for request.toast_message
            if hasattr(request, 'toast_message'):
                toast_data = request.toast_message
                # ic("Found toast_message in request:", toast_data)

                # For API responses (JSON), the toast is already included in the response
                # For other responses, create a ToastNotification record
                is_json_response = False
                if hasattr(response, 'headers'):
                    content_type = response.headers.get('Content-Type', '')
                    is_json_response = 'application/json' in content_type

                if not is_json_response:
                    # Create notification in database if we have a valid place and authenticated user
                    if toast_data and place and hasattr(request, 'user') and request.user.is_authenticated:
                        notification = ToastNotification.objects.create(
                            user=request.user,
                            place=place,
                            message=toast_data['message'],
                            type=toast_data['type']
                        )
                        # ic("notification:", notification)

                    # For redirect responses (302, 301), store toast in session
                    if response.status_code in [301, 302]:
                        if 'pending_toast' not in request.session:
                            request.session['pending_toast'] = toast_data
                            request.session.modified = True
                            # ic("Stored pending_toast in session for redirect:", toast_data)
                    # For TemplateResponse, add to the context
                    elif isinstance(response, TemplateResponse):
                        context_data['toast_message'] = toast_data
                        # ic("Added toast to template context:", toast_data)

        except Exception as e:
            # ic("Create toast notification error:", str(e))
            pass

        try:
            # Handle API responses - these already have toast data in JSON response
            if request.path.startswith('/api/'):
                return response

            # Handle GET with pending toast (after redirect)
            if request.method == 'GET' and isinstance(response, TemplateResponse):
                # Handle pending toast from session
                if 'pending_toast' in request.session:
                    # ic("Processing pending toast from session:", request.session['pending_toast'])
                    pending_toast = request.session.pop('pending_toast')
                    context_data['toast_message'] = pending_toast
                    request.session.modified = True
                    # ic("Added session toast to template context")
                
                # Update unread count if not already set and we have a place
                if place and 'toast_unread_count' not in context_data:
                    user = request.user if hasattr(request, 'user') else None
                    if user and user.is_authenticated:
                        unread_count = ToastNotification.get_unread_count(
                            place=place,
                            user=user,
                        )
                        context_data['toast_unread_count'] = unread_count
                        # ic("unread_count:", unread_count)

        except Exception as e:
            # ic("get unread count error:", str(e))
            pass

        return response

    def process_template_response(self, request, response):
        # Only handle template-specific operations here
        if isinstance(response, TemplateResponse) and not hasattr(response, 'context_data'):
            response.context_data = {}
        return response