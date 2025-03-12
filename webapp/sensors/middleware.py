from icecream import ic
from .models import ToastNotification
from django.db.models import Count

class ToastMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip logging for static and media files
        if not any(path in request.path for path in ['/static/', '/media/']):
            ic("ToastMiddleware processing request")
            ic(request.path)
            ic(request.user.is_authenticated)
            
            if hasattr(request, 'toast_message'):
                ic("Found toast message", request.toast_message)
        
        response = self.get_response(request)
        return response

    def process_template_response(self, request, response):
        if request.path.startswith('/api/') or any(path in request.path for path in ['/static/', '/media/']):
            return response

        if hasattr(response, 'context_data') and request.user.is_authenticated:
            ic("Processing template response")
            ic(request.path)
            
            # Get current unread count
            unread_count = ToastNotification.objects.filter(
                user=request.user,
                read=False
            ).count()
            ic("Unread toast count", unread_count)
            
            # Initialize body_data_attributes if it doesn't exist
            if 'body_data_attributes' not in response.context_data:
                response.context_data['body_data_attributes'] = {}
            
            # Update body data attributes
            response.context_data['body_data_attributes'].update({
                'toast-unread-count': str(unread_count)
            })
            
            # Add count directly to context
            response.context_data['toast_unread_count'] = unread_count
            
            ic("Template context", {
                'toast_unread_count': response.context_data.get('toast_unread_count'),
                'body_data_attributes': response.context_data.get('body_data_attributes')
            })
            
        return response