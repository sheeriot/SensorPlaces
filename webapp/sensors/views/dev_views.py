from django.shortcuts import render, get_object_or_404
from django.http import HttpRequest, HttpResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Q
from sensors.models import Place, Location
import json

def siteplan_test_page(request: HttpRequest, place_slug: str) -> HttpResponse:
    """A view for testing the siteplan card in isolation."""
    place = get_object_or_404(Place, slug=place_slug)

    locations_qs = Location.objects.filter(place=place).exclude(slug='unassigned-devices').annotate(
        devices_total_count=Count('devices'),
        devices_active_count=Count('devices', filter=Q(devices__is_active=True))
    )

    locations_data = []
    for loc in locations_qs:
        locations_data.append({
            "name": loc.name,
            "slug": loc.slug,
            "url": '#', # In a real scenario, this would be reverse('sensors:location_detail', ...)
            "x_pos": loc.x_pos,
            "y_pos": loc.y_pos,
            "is_active": loc.is_active,
            "devices_total_count": loc.devices_total_count,
            "devices_active_count": loc.devices_active_count,
        })

    context = {
        "place": place,
        "locations_json": locations_data,
        "editable": True, # Assume editable for testing
        "siteplan_url_for_debugging": place.get_siteplan_url(),
    }

    return render(request, 'sensors/dev/siteplan_test.html', context)
