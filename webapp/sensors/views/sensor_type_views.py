from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from ..models import SensorType
from ..forms.sensor_type_forms import SensorTypeForm
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from icecream import ic
from .mixins import ReferrerMixin

class SensorTypeListView(ListView):
    model = SensorType
    template_name = 'sensors/sensortype_list.html'

class SensorTypeDetailView(DetailView):
    model = SensorType
    template_name = 'sensors/sensortype_detail.html'

class SensorTypeCreateView(ReferrerMixin, CreateView):
    model = SensorType
    form_class = SensorTypeForm
    template_name = 'sensors/sensortype_form.html'

    def get_cancel_url(self):
        return reverse('sensors:sensortype_list')

class SensorTypeUpdateView(ReferrerMixin, UpdateView):
    model = SensorType
    form_class = SensorTypeForm
    template_name = 'sensors/sensortype_form.html'

    def get_cancel_url(self):
        if hasattr(self, 'object') and self.object:
            return self.object.get_absolute_url()
        return reverse('sensors:sensortype_list')
