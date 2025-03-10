from icecream import ic

class ToastMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code to be executed for each request before the view
        response = self.get_response(request)
        
        # Code to be executed for each request/response after the view
        if hasattr(request, 'toast_message'):
            ic("ToastMiddleware - Adding toast to session:", request.toast_message)
            request.session['toast_message'] = request.toast_message
            request.session.modified = True
        
        return response

    def process_template_response(self, request, response):
        # Add toast message to template context if it exists
        if hasattr(response, 'context_data'):
            if 'toast_message' in request.session:
                toast_message = request.session.pop('toast_message')
                ic("ToastMiddleware - Adding toast to template context:", {
                    'toast_message': toast_message,
                    'has_context_data': hasattr(response, 'context_data'),
                    'template_name': getattr(response, 'template_name', None)
                })
                response.context_data['toast_message'] = toast_message
                request.session.modified = True
        return response 