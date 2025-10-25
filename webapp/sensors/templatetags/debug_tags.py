from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.simple_tag(takes_context=True)
def debug_context(context):
    """Debug the current template context."""
    # Only show in debug mode
    if not context.get('debug', False):
        return ''
    
    # Filter out complex objects that can't be JSON serialized
    filtered_context = {}
    for d in context.dicts:
        for k, v in d.items():
            try:
                if k not in ['view', 'request'] and not k.startswith('_'):
                    json.dumps({k: str(v)})  # Test if serializable
                    filtered_context[k] = str(v)
            except:
                filtered_context[k] = f"<{type(v).__name__}>"
    
    debug_html = f"""
    <div class="debug-context" style="margin-top: 20px; padding: 10px; background: #f8f9fa; border: 1px solid #ddd; border-radius: 5px;">
        <h4>Template Context Debug:</h4>
        <pre>{json.dumps(filtered_context, indent=2)}</pre>
    </div>
    """
    return mark_safe(debug_html) 