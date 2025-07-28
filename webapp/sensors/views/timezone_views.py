from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
@require_POST
def set_user_timezone(request: HttpRequest) -> JsonResponse:
    """
    Sets the user's timezone in the session.
    """
    try:
        data = json.loads(request.body)
        timezone = data.get('timezone')
        if timezone:
            request.session['user_timezone'] = timezone
            return JsonResponse({'status': 'ok'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Timezone not provided'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400) 