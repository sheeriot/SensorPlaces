from django.urls import reverse_lazy, reverse
import json
from urllib.parse import urlencode
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
)
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.mixins import LoginRequiredMixin
import logging
import time

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.db.models import Prefetch, Case, When, BooleanField

from ..models import Place, InfluxStore
from .mixins import PlaceAnnotationMixin, ReferrerMixin
from .influx_forms import InfluxStoreForm
from .sensor_forms import InfluxStoreDeleteForm

from ..influx_client import test_influx_bucket, test_influx_write_read, get_latest_influx_reading
from icecream import ic
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from ..models import InfluxStore, Sensor


@login_required
@require_POST
def test_influx_store_bucket(request, place_slug, pk):
    """
    Tests the basic connection to the bucket for a specific InfluxStore.
    """
    place = get_object_or_404(Place, slug=place_slug)
    store = get_object_or_404(InfluxStore, pk=pk, place=place)

    success, message, query_time_ms = test_influx_bucket(
        url=store.url,
        token=store.token,
        org=store.org,
        bucket_name=store.bucket_name
    )

    return render(request, 'sensors/partials/_influx_test_results.html',
                  {'success': success, 'message': message, 'query_time_ms': query_time_ms, 'test_name': 'Bucket Read Test'})

@login_required
@require_POST
def test_influx_store_write_read_view(request, place_slug, pk):
    """
    Tests the write/read functionality for a specific InfluxStore.
    """
    place = get_object_or_404(Place, slug=place_slug)
    store = get_object_or_404(InfluxStore, pk=pk, place=place)

    start_time = time.time()
    results = test_influx_write_read(store)
    end_time = time.time()
    
    query_time_ms = int((end_time - start_time) * 1000)

    context = {
        'test_name': 'Write/Read Test',
        'query_time_ms': query_time_ms,
        **results
    }

    return render(request, 'sensors/partials/_influx_test_results.html', context)


@login_required
@require_POST
def influxstore_test(request, place_slug, pk, test_type_override=None):
    """
    Unified view for running various tests against an InfluxDB store.
    Handles:
    - 'bucket_read': Basic connection and bucket list test.
    - 'write': A write/read test to a temporary measurement.
    - 'sensor_read': Reads the latest value for a specific sensor.
    """
    store = get_object_or_404(InfluxStore, pk=pk)
    test_type = request.GET.get('test_type') or test_type_override
    context = {}

    if test_type == 'bucket_read':
        success, message, query_time_ms = test_influx_bucket(
            url=store.url,
            token=store.token,
            org=store.org,
            bucket_name=store.bucket_name
        )
        context = {
            'test_name': 'Bucket Read Test',
            'success': success,
            'message': message,
            'query_time_ms': query_time_ms
        }
    elif test_type == 'write':
        start_time = time.time()
        results = test_influx_write_read(store)
        end_time = time.time()
        query_time_ms = int((end_time - start_time) * 1000)
        context = {
            'test_name': 'Write/Read Test',
            'query_time_ms': query_time_ms,
            **results
        }
    elif test_type == 'sensor_read':
        sensor_pk = request.GET.get('sensor_pk')
        sensor = get_object_or_404(Sensor, pk=sensor_pk)
        start_time = time.time()
        results = get_latest_influx_reading(sensor)
        end_time = time.time()
        query_time_ms = int((end_time - start_time) * 1000)
        context = {
            'test_name': 'Read Sensor Data',
            'sensor': sensor,
            'query_time_ms': query_time_ms,
            'results': results,
            'success': True if results and results.get('reading') else False,
            'message': "Successfully read latest sensor data." if results and results.get('reading') else "Could not find sensor data."
        }
    else:
        return HttpResponse("Invalid test type specified.", status=400)

    return render(request, 'sensors/partials/_influx_test_results.html', context)


class InfluxStoreListView(LoginRequiredMixin, PlaceAnnotationMixin, ListView):
    model = InfluxStore
    template_name = "sensors/influxstore_list.html"
    context_object_name = "influxstores"

    def get_queryset(self):
        place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        
        queryset = InfluxStore.objects.filter(place=place)

        # Annotate and order the queryset
        queryset = queryset.annotate(
            is_default=Case(
                When(pk=place.default_influx_store_id, then=True),
                default=False,
                output_field=BooleanField()
            ),
            is_switchbot=Case(
                When(pk=place.switchbot_influx_store_id, then=True),
                default=False,
                output_field=BooleanField()
            )
        ).order_by('-is_default', '-is_switchbot', 'name')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        return context

class InfluxStoreDetailView(DetailView):
    model = InfluxStore
    template_name = "sensors/influxstore_detail.html"
    context_object_name = "influxstore"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = self.object.place
        return context

class InfluxStoreCreateView(LoginRequiredMixin, ReferrerMixin, CreateView):
    model = InfluxStore
    form_class = InfluxStoreForm
    template_name = "sensors/influxstore_form.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.place = get_object_or_404(Place, slug=self.kwargs['place_slug'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        initial = kwargs.get('initial', {})
        initial['place'] = self.place
        initial['referrer'] = self.request.META.get('HTTP_REFERER', '')
        kwargs['initial'] = initial
        kwargs['cancel_url'] = self.request.META.get('HTTP_REFERER') or reverse("sensors:place_detail", kwargs={'place_slug': self.place.slug})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = self.place
        return context

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ["sensors/influxstore_form_modal.html"]
        return [self.template_name]

    def get_success_url(self):
        return self.request.POST.get('referrer') or reverse("sensors:place_detail", kwargs={'place_slug': self.place.slug})

    def get_cancel_url(self):
        return reverse("sensors:place_detail", kwargs={'place_slug': self.kwargs['place_slug']})

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'pk': self.object.pk,
                'name': self.object.name,
            })
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'html': render_to_string(self.template_name, {'form': form}, request=self.request),
            })
        return super().form_invalid(form)


class InfluxStoreUpdateView(LoginRequiredMixin, ReferrerMixin, UpdateView):
    model = InfluxStore
    form_class = InfluxStoreForm
    template_name = "sensors/influxstore_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cancel_url'] = self.get_cancel_url()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'form' not in context:
            context['form'] = self.get_form()
        return context

    def get_success_url(self):
        return reverse("sensors:place_detail", kwargs={'place_slug': self.object.place.slug})

    def get_cancel_url(self):
        return self.object.get_absolute_url()


class InfluxStoreDeleteView(LoginRequiredMixin, PlaceAnnotationMixin, FormView):
    template_name = 'sensors/partials/influxstore_confirm_delete_modal.html'
    form_class = InfluxStoreDeleteForm

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.object = get_object_or_404(InfluxStore, pk=self.kwargs['pk'], place__slug=self.kwargs['place_slug'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['store_name'] = self.object.name
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object'] = self.object
        context['place'] = self._place
        return context

    def form_valid(self, form):
        store_name = self.object.name
        self.object.delete()
        messages.success(self.request, f"InfluxDB Store '{store_name}' has been deleted.")

        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('sensors:place_detail', kwargs={'place_slug': self.kwargs['place_slug']})
        return response
