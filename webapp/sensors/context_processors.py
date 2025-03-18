from icecream import ic

def toast_messages(request):
    """
    Context processor that adds toast messages to template context.
    """
    context = {}
    
    # Check if the request contains a session with pending_toast
    if hasattr(request, 'session') and 'pending_toast' in request.session:
        context['toast_message'] = request.session.pop('pending_toast')
        request.session.modified = True
    
    # Also check for toast_message attribute on request
    if hasattr(request, 'toast_message'):
        context['toast_message'] = request.toast_message
    
    return context 