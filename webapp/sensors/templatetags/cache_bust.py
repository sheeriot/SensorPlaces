from django.conf import settings
from django import template
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def bust(path):
    """
    Appends a timestamp to a URL for cache busting.
    """
    url = static(path)
    return f"{url}?v={settings.CACHE_VERSION}"
