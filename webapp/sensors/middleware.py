from icecream import ic

class ToastMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code to be executed for each request before the view
        response = self.get_response(request)
        
        # Code to be executed for each request/response after the view
        if hasattr(request, 'toast_message'):
            ic("ToastMiddleware - Adding toast to history:", request.toast_message)
            
            # Initialize or get existing history
            toast_history = request.session.get('toast_history', [])
            
            # Add new message to the beginning of the history
            toast_history.insert(0, request.toast_message)
            
            # Limit history to 50 items to prevent session from growing too large
            toast_history = toast_history[:50]
            
            # Store updated history
            request.session['toast_history'] = toast_history
            request.session.modified = True
            
            # Also store current message for immediate display
            request.session['current_toast'] = request.toast_message
        
        return response

    def process_template_response(self, request, response):
        # Add toast message to template context if it exists
        if hasattr(response, 'context_data'):
            # Handle current toast for immediate display
            if 'current_toast' in request.session:
                current_toast = request.session.pop('current_toast')
                ic("ToastMiddleware - Adding current toast to template context:", {
                    'current_toast': current_toast,
                    'has_context_data': hasattr(response, 'context_data'),
                    'template_name': getattr(response, 'template_name', None)
                })
                response.context_data['toast_message'] = current_toast
                request.session.modified = True
                
            # Add full history to context
            toast_history = request.session.get('toast_history', [])
            response.context_data['toast_history'] = toast_history
            
        return response 