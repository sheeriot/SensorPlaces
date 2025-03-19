from django.shortcuts import get_object_or_404

from .models import Place, Location, Device, Sensor, ToastNotification
from .views.views_fun import get_place_data
# from .views.mixins import PlaceAnnotationMixin

import json

from icecream import ic

def place_context(request):
    """
    Context processor that adds place and related data to template context.
    """
    context = {}
    # Try to get place_slug from URL kwargs if available
    place_slug = None
    if hasattr(request, 'resolver_match') and request.resolver_match:
        place_slug = request.resolver_match.kwargs.get('place_slug', None)
    
    # Make place_slug available in context
    context['place_slug'] = place_slug
    
    # If we have place_slug, try to get Place object and unread toast count
    if place_slug:
        try:
            place = get_object_or_404(Place, slug=place_slug)
            context['place'] = place
            
            # Get unread toast count if user is authenticated
            if hasattr(request, 'user') and request.user.is_authenticated:
                context['toast_unread_count'] = ToastNotification.get_unread_count(
                    place=place,
                    user=request.user,
                )
            
            # Add all place data
            context.update(get_place_data(place))
            
        except Exception:
            # Don't fail if place not found, as this is just a context processor
            pass
    
    return context

def toast_messages(request):
    """
    Context processor that adds toast messages to template context.
    """
    context = {}
    
    # Check if the request contains a session with pending_toast
    if hasattr(request, 'session') and 'pending_toast' in request.session:
        context['toast_message'] = request.session.pop('pending_toast')
        request.session.modified = True
    
    # Also check for toast_message attribute on request
    if hasattr(request, 'toast_message'):
        context['toast_message'] = request.toast_message
    
    return context 