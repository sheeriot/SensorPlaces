from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, render

from ..models import InfluxSource, Place
from .influx_forms import InfluxSourceForm


class InfluxSourceListView(ListView):
    model = InfluxSource
    template_name = "sensors/influxsource_list.html"
    context_object_name = "influxsources"

    def get_queryset(self):
        place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        return InfluxSource.objects.filter(place=place)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        return context

class InfluxSourceDetailView(DetailView):
    model = InfluxSource
    template_name = "sensors/influxsource_detail.html"
    context_object_name = "influxsource"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = self.object.place
        return context

class InfluxSourceCreateView(CreateView):
    model = InfluxSource
    form_class = InfluxSourceForm
    template_name = "sensors/influxsource_form.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.place = get_object_or_404(Place, slug=self.kwargs['place_slug'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = {'place': self.place}
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = self.place
        return context
    
    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ["sensors/influxsource_form_modal.html"]
        return [self.template_name]

    def get_success_url(self):
        return reverse("sensors:influxsource_list", kwargs={'place_slug': self.place.slug})

    def form_valid(self, form):

        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'html': render_to_string(self.template_name, {'form': form}, request=self.request),
            })
        return super().form_invalid(form)


class InfluxSourceUpdateView(UpdateView):
    model = InfluxSource
    template_name = "sensors/influxsource_form.html"
    fields = ["name", "url", "org", "bucket_name", "token"]
    success_url = reverse_lazy("sensors:influxsource_list")

class InfluxSourceDeleteView(DeleteView):
    model = InfluxSource
    template_name = "sensors/influxsource_confirm_delete.html"
    context_object_name = "influxsource"

    def get_object(self, queryset=None):
        place = get_object_or_404(Place, slug=self.kwargs['place_slug'])
        return get_object_or_404(InfluxSource, pk=self.kwargs['pk'], place=place)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = self.object.place
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            context = self.get_context_data(object=self.object)
            html = render_to_string("sensors/influxsource_confirm_delete_modal.html", context, request=request)
            return JsonResponse({'html': html})
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return HttpResponse(status=204, headers={'HX-Redirect': self.get_success_url()})
    
    def get_success_url(self):
        return self.request.POST.get('next', reverse("sensors:influxsource_list", kwargs={'place_slug': self.object.place.slug}))
 