from icecream import ic
from .models import ToastNotification
from django.db.models import Count

class ToastMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Only process toast messages for authenticated users
        if hasattr(request, 'toast_message') and request.user.is_authenticated:
            toast_msg = request.toast_message
            # ic("ToastMiddleware - Adding toast to history:", toast_msg)
            
            # Store current message for immediate display
            request.session['current_toast'] = toast_msg
            
            # Database persistence with user
            ToastNotification.objects.create(
                user=request.user,
                message=toast_msg['message'],
                type=toast_msg['type'],
                read=False  # New notifications are unread by default
            )
        
        return response

    def process_template_response(self, request, response):
        # Add toast message to template context if it exists
        if hasattr(response, 'context_data') and request.user.is_authenticated:
            # Handle current toast for immediate display
            if 'current_toast' in request.session:
                current_toast = request.session.pop('current_toast')
                response.context_data['toast_message'] = current_toast
                request.session.modified = True
            
            # Get toast history and unread count
            toast_history = ToastNotification.objects.filter(
                user=request.user
            ).order_by('-created_at')
            
            unread_count = toast_history.filter(read=False).count()
            
            # Add to context for template use
            response.context_data['toast_history'] = toast_history
            response.context_data['unread_toast_count'] = unread_count
            
            # Add to body data attributes for JavaScript
            response.context_data['body_data_attributes'] = {
                'unreadToasts': str(unread_count),
                **response.context_data.get('body_data_attributes', {})
            }
            
        return response