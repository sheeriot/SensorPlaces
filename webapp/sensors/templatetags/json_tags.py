import json
from django import template
from django.utils.html import format_html, mark_safe
from django.contrib.humanize.templatetags.humanize import naturaltime
from datetime import datetime, timezone as dt_timezone

register = template.Library()


@register.filter(name='to_json')
def to_json(value):
    """
    Convert a Python object to JSON string for use in data attributes.
    Uses HTML entity escaping that browsers will decode automatically.
    """
    try:
        # json.dumps produces valid JSON, then we let Django escape it for HTML attributes
        # The browser's dataset API will decode the HTML entities back to the original JSON
        return json.dumps(value)
    except (TypeError, ValueError):
        return '[]'

def _generate_html_from_dict(data, level=0):
    """
    Recursively generates a nested HTML list from a dictionary for pretty display.
    """
    if not isinstance(data, dict):
        return format_html('{}', data)

    # Define a preferred order for top-level keys
    preferred_order = [
        'scraped_model_name',
        'firmware_version',
        'client_ip',
        'request_url',
        'request_headers',
        'scraped_at',
    ]

    # Custom sort function
    def sort_keys(item):
        key = item[0]
        if key in preferred_order:
            return (preferred_order.index(key), key)
        return (len(preferred_order), key)

    # Sort items based on the level. Only apply custom sort to the top level.
    items = sorted(data.items(), key=sort_keys) if level == 0 else sorted(data.items())

    parts = ['<ul class="list-unstyled mb-0">']
    for key, value in items:
        # Use the key as the label, replacing underscores
        label = str(key).replace('_', ' ')

        if key == 'scraped_at':
            try:
                # Parse the ISO 8601 timestamp string
                ts = datetime.fromisoformat(value.replace('Z', '+00:00'))
                # Format it with natural time
                natural_ts = naturaltime(ts)
                parts.append(format_html(
                    '<li><small><span class="text-muted small text-capitalize">{}:</span> {} ({})</small></li>',
                    label,
                    value,
                    natural_ts
                ))
            except (ValueError, TypeError):
                # Fallback for invalid timestamp format
                parts.append(format_html(
                    '<li><small><span class="text-muted small text-capitalize">{}:</span> {}</small></li>',
                    label,
                    value
                ))
            continue

        if isinstance(value, dict):
            # If the value is another dictionary, recurse
            parts.append(format_html(
                '<li><div class="text-muted small text-capitalize">{}:</div><div class="ps-3">{}</div></li>',
                label,
                _generate_html_from_dict(value, level + 1)
            ))
        else:
            # Otherwise, display the key-value pair
            parts.append(format_html(
                '<li><span class="text-muted small text-capitalize">{}:</span> {}</li>',
                label,
                value
            ))
    parts.append('</ul>')
    return mark_safe(''.join(parts))

@register.filter(name='format_scraped_data', is_safe=True)
def format_scraped_data(device):
    """
    Formats the scraped_data JSON for pretty display in a template.
    """
    if not device or not device.scraped_data:
        return "No data available"

    data = device.scraped_data
    return _generate_html_from_dict(data)
