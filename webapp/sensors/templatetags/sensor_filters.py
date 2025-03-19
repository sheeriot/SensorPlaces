from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_LEAFLET_LOADED = False

@register.filter
def filter_active(locations):
    """Filter to return active locations."""
    return [location for location in locations if location.is_active]  # Adjust according to your model

@register.filter
def filter_inactive(queryset):
    return [obj for obj in queryset if not obj.is_active]

@register.filter
def subtract(value, arg):
    return value - arg

@register.simple_tag
def load_leaflet_once():
    return ''  # Deprecated - Leaflet is now loaded in base.html 

@register.filter
def filter_active_count(locations):
    """Filter and count active locations"""
    return sum(1 for loc in locations if loc.is_active)

@register.filter
def filter_inactive_count(locations):
    """Filter and count inactive locations"""
    return sum(1 for loc in locations if not loc.is_active)

@register.filter
def add(value, arg):
    """Add the arg to the value."""
    try:
        return value + arg
    except (ValueError, TypeError):
        try:
            return int(value) + int(arg)
        except (ValueError, TypeError):
            return "" 