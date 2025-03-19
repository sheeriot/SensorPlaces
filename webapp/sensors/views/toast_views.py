from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from django.shortcuts import get_object_or_404
from django.db.models import Exists, OuterRef
from django.http import JsonResponse
from django.views.generic import ListView

from ..models import Place, ToastNotification, ToastReadStatus

import json


# Add the ToastListView class
class ToastListView(LoginRequiredMixin, ListView):
    """View for displaying a list of toast notifications for a place."""
    model = ToastNotification
    template_name = 'sensors/toast_list.html'
    context_object_name = 'toasts'
    paginate_by = 20
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.place = get_object_or_404(Place, slug=kwargs.get('place_slug'))
    
    def get_queryset(self):
        return ToastNotification.objects.filter(
            user=self.request.user,
            place=self.place
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = self.place
        context['model_name'] = 'toast'
        return context


@method_decorator(csrf_protect, name='dispatch')
class ToastAPIView(LoginRequiredMixin, View):
    """Single API endpoint for all toast-related operations."""
    
    def get(self, request, place_slug):
        """Handle GET requests for toast messages.
        
        Query Parameters:
            show_all: bool - If True, return all messages, if False only unread
        """
        try:
            place = get_object_or_404(Place, slug=place_slug)
            show_all = request.GET.get('show_all', 'false').lower() == 'true'
            
            # Base query with read status annotation
            notifications = ToastNotification.objects.filter(
                user=request.user,
                place=place
            ).annotate(
                read=Exists(
                    ToastReadStatus.objects.filter(
                        user=request.user,
                        toast_id=OuterRef('pk')
                    )
                )
            )
            
            # Filter unread if not showing all
            if not show_all:
                notifications = notifications.filter(
                    ~Exists(ToastReadStatus.objects.filter(
                        user=request.user,
                        toast_id=OuterRef('pk')
                    ))
                )
            
            # Get the last 50 notifications
            history = notifications.order_by('-created_at')[:50].values(
                'id',
                'message',
                'type',
                'created_at',
                'read'
            )
            
            return JsonResponse({
                'success': True,
                'history': list(history),
                'unread_count': ToastNotification.get_unread_count(
                    user=request.user,
                    place=place
                )
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    def post(self, request, place_slug):
        """Handle POST requests for marking messages as read.
        
        POST Data:
            action: str - 'mark_read'
            toast_ids: int or list[int] - Single ID or list of IDs to mark as read
        """
        try:
            place = get_object_or_404(Place, slug=place_slug)
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'mark_read':
                toast_ids = data.get('toast_ids')
                if not toast_ids:
                    return JsonResponse({
                        'success': False,
                        'error': 'toast_ids is required'
                    }, status=400)
                
                # Convert single ID to list
                if isinstance(toast_ids, int):
                    toast_ids = [toast_ids]
                
                # Verify all toasts belong to this place and user
                toasts = ToastNotification.objects.filter(
                    id__in=toast_ids,
                    user=request.user,
                    place=place
                )
                
                if len(toasts) != len(toast_ids):
                    raise PermissionDenied("Some toast messages don't belong to this place or user")
                
                # Mark toasts as read
                for toast in toasts:
                    ToastReadStatus.objects.get_or_create(
                        user=request.user,
                        toast=toast
                    )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Marked {len(toasts)} messages as read',
                    'unread_count': ToastNotification.get_unread_count(
                        user=request.user,
                        place=place
                    )
                })
            
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Unknown action: {action}'
                }, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON'
            }, status=400)
        except PermissionDenied as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=403)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
