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
        return self.process_response(request, response)

    # resolved: ResolverMatch(func=sensors.views.location_views.LocationCreateView, args=(), kwargs={'place_slug': 'carpet'}, 
    #                         url_name='location_create', app_names=['sensors'], namespaces=['sensors'], route='<slug:place_slug>/location/create/',
    #                         captured_kwargs={'place_slug': 'carpet'})

    def process_response(self, request, response):
        ic('=======> Toast Middleware process_response', request.path)
        if any(path in request.path for path in ['/static/', '/media/']):
            return response
        try:
            ic(request)      
            ic(request.resolver_match)
            ic(request.resolver_match.kwargs)
            place_slug = request.resolver_match.kwargs.get('place_slug', None)
            if place_slug:
                place = get_object_or_404(Place, slug=place_slug)
                ic(place)

            toast_data = None
            
            # Check for request.toast_message
            if hasattr(request, 'toast_message'):
                toast_data = request.toast_message
                ic("Found toast_message in request:", toast_data)

            # Create notification in database if toast_data is available
            if toast_data:
                notification = ToastNotification.objects.create(
                    user=request.user,
                    place=place,
                    message=toast_data['message'],
                    type=toast_data['type']
                )
                ic(notification)

            # Handle API responses
            if request.path.startswith('/api/'):
                return response

            # Handle GET with pending toast (after redirect)
            elif request.method == 'GET' and isinstance(response, TemplateResponse):
                # Update unread count
                unread_count = ToastNotification.get_unread_count(
                    place=place,
                    user=request.user,
                )
                response.context_data['toast_unread_count'] = unread_count
                ic("Updated unread count:", unread_count)

                # Process pending toast
                if 'pending_toast' in request.session:
                    toast_data = request.session.pop('pending_toast')
                    response.context_data['toast_message'] = toast_data

        except Exception as e:
            ic("Toast Middleware error:", str(e))

        return response

    def process_template_response(self, request, response):
        if request.path.startswith('/api/') or any(path in request.path for path in ['/static/', '/media/']):
            return response
        
        # ic("** Middleware - Process template response:")
        # ic(request.path)
        # ic(place_slug)
        # if hasattr(response, 'context_data'):
        #     ic(response.context_data)
        # if hasattr(request, 'toast_message'):
        #     ic(request.session.toast_message)

        if hasattr(response, 'context_data') and request.user.is_authenticated:
            try:
                # Get place_slug from URL kwargs
                resolved = resolve(request.path)
                # ic(request.path, resolved)
                place_slug = resolved.kwargs.get('place_slug')

                
                # Add place_slug to context data
                response.context_data['place_slug'] = place_slug
                
                # Get unread count - only if we have a place
                if place_slug:
                    place = get_object_or_404(Place, slug=place_slug)
                    unread_count = ToastNotification.get_unread_count(
                        user=request.user,
                        place=place
                    )
                    response.context_data['toast_unread_count'] = unread_count
                    # ic("Updated unread count for place:", {
                    #     'place': place.name,
                    #     'unread_count': unread_count,
                    #     'place_slug': place_slug  # Log the slug too
                    # })
                
                # If there's a pending toast, add it to template context
                if 'pending_toast' in request.session:
                    toast_data = request.session.pop('pending_toast')
                    # ic("Processing pending toast in template:", toast_data)
                    
                    # Add to template context instead of messages
                    response.context_data['toast_message'] = toast_data
                    # ic("Added toast to template context:", {
                        # 'toast_data': toast_data,
                        # 'context_keys': list(response.context_data.keys())
                    # })
                
                # ic("Template response context complete:", {
                #     'has_messages': bool(list(messages.get_messages(request))),
                #     'context_keys': list(response.context_data.keys())
                # })
                
            except Exception as e:
                ic("Template response error:", {
                    'error': str(e),
                    'path': request.path
                })
        
        return response