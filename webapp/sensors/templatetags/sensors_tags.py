from django import template

register = template.Library()

@register.filter
def pop_session_key(session, key):
    """Pop a key from the session and return None.
    
    Usage:
        {{ request.session|pop_session_key:'key_name' }}
    """
    if key in session:
        session.pop(key)
        session.modified = True
    return '' 