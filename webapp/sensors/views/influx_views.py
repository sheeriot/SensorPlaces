from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)

from ..models import InfluxSource

class InfluxSourceListView(ListView):
    model = InfluxSource
    template_name = "sensors/influxsource_list.html"
    context_object_name = "influxsource_list"

class InfluxSourceDetailView(DetailView):
    model = InfluxSource
    template_name = "sensors/influxsource_detail.html"
    context_object_name = "influxsource"

class InfluxSourceCreateView(CreateView):
    model = InfluxSource
    template_name = "sensors/influxsource_form.html"
    fields = ["name", "url", "org", "bucket_name", "token"]
    success_url = reverse_lazy("sensors:influxsource_list")

class InfluxSourceUpdateView(UpdateView):
    model = InfluxSource
    template_name = "sensors/influxsource_form.html"
    fields = ["name", "url", "org", "bucket_name", "token"]
    success_url = reverse_lazy("sensors:influxsource_list")

class InfluxSourceDeleteView(DeleteView):
    model = InfluxSource
    template_name = "sensors/influxsource_confirm_delete.html"
    success_url = reverse_lazy("sensors:influxsource_list") 