from django import template
from django.utils import timezone
import datetime
from datetime import timezone as dt_timezone

register = template.Library()

@register.filter
def format_timestamp_with_timezone(timestamp):
    if not timestamp:
        return "N/A"

    if isinstance(timestamp, str):
        try:
            timestamp = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return "Invalid timestamp"

    # If the timestamp is naive, assume it's in UTC
    if timezone.is_naive(timestamp):
        timestamp = timezone.make_aware(timestamp, dt_timezone.utc)

    # Convert to user's local timezone
    local_timestamp = timezone.localtime(timestamp)

    # Format the timestamp
    date_str = local_timestamp.strftime('%Y/%m/%d')
    time_str = local_timestamp.strftime('%H:%M:%S')

    # Get timezone info
    tz_name = local_timestamp.tzname()

    # Get offset in compact format
    offset_seconds = local_timestamp.utcoffset().total_seconds()
    offset_hours = int(offset_seconds // 3600)
    offset_minutes = int((offset_seconds % 3600) // 60)
    offset_string = f"{'+' if offset_seconds >= 0 else '-'}{abs(offset_hours):02d}{abs(offset_minutes):02d}"

    return f"{date_str} {time_str} {offset_string} ({tz_name})"
