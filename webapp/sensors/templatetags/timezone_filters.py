from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe
import sqlparse
from datetime import datetime as dt
import datetime
from datetime import timezone as dt_timezone
import pytz
from icecream import ic
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

register = template.Library()

@register.filter
def utc_to_local_time(utc_dt, tz_name=None):
    """
    Converts a UTC datetime object to a local datetime object.
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
def format_timestamp_with_timezone(timestamp, user_timezone_str='UTC'):
    """
    Formats a timezone-aware datetime object into a string with the user's
    local timezone, offset, and timezone name.
    """
    if not timestamp:
        return ""

    if not isinstance(timestamp, dt):
        return str(timestamp)

    try:
        user_tz = ZoneInfo(user_timezone_str)
    except ZoneInfoNotFoundError:
        user_tz = ZoneInfo('UTC')

    local_dt = timestamp.astimezone(user_tz)

    date_str = local_dt.strftime('%Y/%m/%d')
    time_str = local_dt.strftime('%H:%M:%S')
    tz_name = local_dt.tzname()
    offset_string = local_dt.strftime('%z')

    return f"{date_str} {time_str} {offset_string} ({tz_name})"

@register.filter
def isoformat(value):
    """Formats a datetime object to an ISO 8601 string."""
    if value and hasattr(value, 'isoformat'):
        return value.isoformat()
    return value
