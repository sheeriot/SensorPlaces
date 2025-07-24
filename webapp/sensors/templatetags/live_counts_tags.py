from django import template
from ..views.views_fun import get_place_counts

register = template.Library()

@register.inclusion_tag('sensors/includes/live_counts_card.html', takes_context=True)
def live_counts_card(context, place):
    locations_active, locations_inactive, devices_active, devices_inactive, sensors_active, sensors_inactive = get_place_counts(place)
    return {
        'place': place,
        'locations_active_count': locations_active,
        'locations_inactive_count': locations_inactive,
        'devices_active_count': devices_active,
        'devices_inactive_count': devices_inactive,
        'sensors_active_count': sensors_active,
        'sensors_inactive_count': sensors_inactive
    } 