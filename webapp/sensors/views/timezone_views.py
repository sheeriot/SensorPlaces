from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from icecream import ic

@csrf_exempt
@require_POST
def set_user_timezone(request: HttpRequest) -> JsonResponse:
    """
    Sets the user's timezone in the session.
    """
    ic("--- set_user_timezone view ---")
    try:
        data = json.loads(request.body)
        timezone = data.get('timezone')
        ic(f"Received timezone from client: {timezone}")
        if timezone:
            request.session['user_timezone'] = timezone
            ic(f"Set session 'user_timezone' to: {request.session['user_timezone']}")
            # Manually save the session to ensure it's written
            request.session.save()
            return JsonResponse({'status': 'ok'})
        else:
            ic("-> No timezone provided in request body.")
            return JsonResponse({'status': 'error', 'message': 'Timezone not provided'}, status=400)
    except json.JSONDecodeError:
        ic("-> Invalid JSON in request body.")
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
