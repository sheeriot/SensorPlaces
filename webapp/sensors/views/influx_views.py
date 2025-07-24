from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404

from ..models import InfluxSource, Place
from .influx_forms import InfluxSourceForm

from icecream import ic

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
        ic("Form is valid")
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            ic("AJAX request detected, returning JSON")
            return JsonResponse({
                'success': True,
                'pk': self.object.pk,
                'name': self.object.name,
            })
        ic("Standard request, redirecting")
        return super().form_valid(form)

    def form_invalid(self, form):
        ic("Form is invalid")
        ic(form.errors)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            ic("AJAX request detected, returning JSON error")
            return JsonResponse({
                'success': False,
                'html': render_to_string(self.template_name, {'form': form}, request=self.request),
            })
        ic("Standard request, re-rendering form")
        return super().form_invalid(form)


class InfluxSourceUpdateView(UpdateView):
    model = InfluxSource
    template_name = "sensors/influxsource_form.html"
    fields = ["name", "url", "org", "bucket_name", "token"]
    success_url = reverse_lazy("sensors:influxsource_list")

class InfluxSourceDeleteView(DeleteView):
    model = InfluxSource
    template_name = "sensors/influxsource_confirm_delete.html"
    success_url = reverse_lazy("sensors:influxsource_list") 