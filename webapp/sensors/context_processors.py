from django.conf import settings
from django.utils import timezone
from icecream import ic

def app_version_processor(request):
    """
    Adds the application's cache version to the template context.
    """
    return {'APP_VERSION': settings.APP_VERSION}

def timezone_context_processor(request):
    """
    Makes the user's timezone available in the template context.
    It prioritizes the cookie, as it's more reliable for HTMX requests,
    and falls back to the session.
    """
    user_timezone = request.COOKIES.get('user_timezone')
    source = 'cookie'

    if not user_timezone:
        user_timezone = request.session.get('user_timezone', 'UTC')
        source = 'session'

    # ic(f"[Context Processor] Found timezone '{user_timezone}' from '{source}'.")

    return {
        'user_timezone': user_timezone
    }
