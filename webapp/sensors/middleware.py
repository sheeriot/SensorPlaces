from django.urls import resolve
from django.contrib import messages
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

from .models import Place, ToastNotification

import json
from icecream import ic

class ToastMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Handle toast messages for any response type
        if hasattr(request, 'user') and request.user.is_authenticated:
            if 'toast_messages' in request.session:
                # Get place from URL - source of truth
                place = None
                place_slug = None

                if hasattr(request, 'resolver_match') and request.resolver_match:
                    place_slug = request.resolver_match.kwargs.get('place_slug', None)

                if place_slug:
                    try:
                        place = Place.objects.get(slug=place_slug)
                    except Place.DoesNotExist:
                        pass

                for toast_data in request.session['toast_messages']:
                    notification = ToastNotification.objects.create(
                        user=request.user,
                        place=place,  # This may be None but should ideally always have a place
                        message=toast_data['message'],
                        type=toast_data['type']
                    )

                # Clear the messages after processing
                del request.session['toast_messages']
                request.session.modified = True

        # Process response for toast messages
        return self.process_response(request, response)

    def process_response(self, request, response):
        # do not process static files or media files
        if any(path in request.path for path in ['/static/', '/media/']):
            return response

        # Get place_slug from URL - source of truth
        place_slug = None
        if hasattr(request, 'resolver_match') and request.resolver_match:
            place_slug = request.resolver_match.kwargs.get('place_slug', None)

        # Add DIRECT data to the response if it's a redirect with toast
        if hasattr(request, 'toast_message') and response.status_code in [301, 302]:
            # Store toast directly in the session for guaranteed access
            if 'pending_toast' not in request.session:
                request.session['pending_toast'] = request.toast_message
                request.session.modified = True

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

        # Get place and add unread_count (should be handled by context processor now)
        place = None
        if place_slug:
            try:
                place = Place.objects.get(slug=place_slug)
            except Place.DoesNotExist:
                pass

        try:
            # Check for request.toast_message
            if hasattr(request, 'toast_message'):
                toast_data = request.toast_message

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

                # For TemplateResponse, add to the context
                elif isinstance(response, TemplateResponse):
                    # Initialize toast_messages as a list in context if it doesn't exist
                    if 'toast_messages' not in context_data:
                        context_data['toast_messages'] = []

                    # Add all toast messages to the context list
                    context_data['toast_messages'].extend(toast_data)

        except Exception:
            # Just pass - we don't want to break the response over toast issues
            pass

        try:
            # Handle API responses - these already have toast data in JSON response
            if request.path.startswith('/api/'):
                return response

            # Handle GET with pending toast (after redirect)
            if request.method == 'GET' and isinstance(response, TemplateResponse):
                # Handle pending toast from session
                if 'toast_messages' in request.session:
                    # Initialize toast_messages in context if not present
                    if 'toast_messages' not in context_data:
                        context_data['toast_messages'] = []

                    # Add session messages to context
                    pending_toasts = request.session.pop('toast_messages')
                    context_data['toast_messages'].extend(pending_toasts)
                    request.session.modified = True

        except Exception:
            # Just pass - we don't want to break the response over toast issues
            pass

        return response

    def process_template_response(self, request, response):
        # Only handle template-specific operations here
        if isinstance(response, TemplateResponse) and not hasattr(response, 'context_data'):
            response.context_data = {}
        return response

class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_timezone = request.session.get('user_timezone')
        if user_timezone:
            timezone.activate(user_timezone)
        else:
            timezone.deactivate()

        response = self.get_response(request)

        # Deactivate the timezone after the response is processed
        timezone.deactivate()

        return response
