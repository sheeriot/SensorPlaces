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
    global _LEAFLET_LOADED
    if not _LEAFLET_LOADED:
        _LEAFLET_LOADED = True
        return mark_safe('''
            <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
        ''')
    return '' 