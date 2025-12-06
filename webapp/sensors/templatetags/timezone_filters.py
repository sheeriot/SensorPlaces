from django import template
from django.utils import timezone
import datetime
from datetime import timezone as dt_timezone
import pytz

register = template.Library()

@register.filter
def utc_to_local_time(utc_dt, tz_name=None):
    """
    Converts a UTC datetime object to a local timezone.
    If tz_name is provided, it uses that timezone.
    Otherwise, it uses Django's current timezone.
    """
    if not utc_dt:
        return None

    if isinstance(utc_dt, str):
        try:
            utc_dt = datetime.datetime.fromisoformat(utc_dt.replace('Z', '+00:00'))
        except ValueError:
            return utc_dt

    if timezone.is_naive(utc_dt):
        utc_dt = timezone.make_aware(utc_dt, dt_timezone.utc)
    else:
        utc_dt = utc_dt.astimezone(dt_timezone.utc)

    if tz_name:
        try:
            local_tz = pytz.timezone(tz_name)
            return utc_dt.astimezone(local_tz)
        except pytz.UnknownTimeZoneError:
            return timezone.localtime(utc_dt)
    
    return timezone.localtime(utc_dt)

@register.filter
def pretty_sql(value):
    """
    A simple SQL pretty-printer.
    """
    if not isinstance(value, str):
        return value
    
    return value.replace(' FROM ', '\nFROM ').replace(' WHERE ', '\nWHERE ').replace(' ORDER BY ', '\nORDER BY ').replace(' LIMIT ', '\nLIMIT ')

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
