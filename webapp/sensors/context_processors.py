from django.conf import settings

def app_version_processor(request):
    """
    Adds the application's cache version to the template context.
    """
    return {'APP_VERSION': settings.APP_VERSION}
