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

        return response

    # resolved: ResolverMatch(func=sensors.views.location_views.LocationCreateView, args=(), kwargs={'place_slug': 'carpet'}, 
    #                         url_name='location_create', app_names=['sensors'], namespaces=['sensors'], route='<slug:place_slug>/location/create/',
    #                         captured_kwargs={'place_slug': 'carpet'})

    def process_response(self, request, response):
        # do not process static files or media files
        if any(path in request.path for path in ['/static/', '/media/']):
            return response
        
        # Get place_slug from URL - source of truth
        place_slug = request.resolver_match.kwargs.get('place_slug', None)    
            # If we have a TemplateResponse, ensure place_slug is in context
        ic(vars(response))
        if isinstance(response, TemplateResponse):
            response.context_data['place_slug'] = place_slug or 'none'
            ic('is template response', place_slug)

        place = None
        try:
            place = get_object_or_404(Place, slug=place_slug)
            ic("place:", place)
            unread_count = ToastNotification.get_unread_count(
                place=place,
                user=request.user,
            )
            response.context_data['toast_unread_count'] = unread_count
        except Exception as e:
            ic(f"Toast Middleware Error: {e}")

        toast_data = None
        try:
            # Check for request.toast_message
            if hasattr(request, 'toast_message'):
                toast_data = request.toast_message
                ic("Found toast_message in request:", toast_data)

            if toast_data and place:
                notification = ToastNotification.objects.create(
                    user=request.user,
                    place=place,
                    message=toast_data['message'],
                    type=toast_data['type']
                )
                ic("notification:", notification)

        except Exception as e:
            ic("Create toast notification error:", str(e))

        try:
            # Handle API responses
            if request.path.startswith('/api/'):
                return response

            # Handle GET with pending toast (after redirect)
            if request.method == 'GET' and isinstance(response, TemplateResponse):
                # Update unread count
                unread_count = ToastNotification.get_unread_count(
                    place=place,
                    user=request.user,
                )
                ic("unread_count:", unread_count)
            response.context_data['toast_unread_count'] = unread_count

        except Exception as e:
            ic("get unread count error:", str(e))
        
        try:
            if 'pending_toast' in request.session:
                ic("Processing pending toast in template:", toast_data)
                toast_data = request.session.pop('pending_toast')
                response.context_data['toast_message'] = toast_data
                ic("Added toast to template context", toast_data)

        except Exception as e:
            ic("Toast Middleware error:", str(e))

        return response

    def process_template_response(self, request, response):
        # Only handle template-specific operations here
        if hasattr(response, 'context_data'):
            # Add any template-specific context here
            pass
        return response