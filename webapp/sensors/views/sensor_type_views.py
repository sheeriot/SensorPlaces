from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from ..models import SensorType
from ..forms.sensor_type_forms import SensorTypeForm
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from icecream import ic

class SensorTypeListView(ListView):
    model = SensorType
    template_name = 'sensors/sensortype_list.html'

class SensorTypeDetailView(DetailView):
    model = SensorType
    template_name = 'sensors/sensortype_detail.html'

class SensorTypeCreateView(CreateView):
    model = SensorType
    form_class = SensorTypeForm
    template_name = 'sensors/sensortype_form.html'
    success_url = reverse_lazy('sensors:sensortype_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cancel_url'] = reverse_lazy('sensors:sensortype_list')
        return kwargs

class SensorTypeUpdateView(UpdateView):
    model = SensorType
    form_class = SensorTypeForm
    template_name = 'sensors/sensortype_form.html'

    def get_success_url(self):
        return reverse_lazy('sensors:sensortype_detail', kwargs={'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cancel_url'] = self.get_success_url()
        return kwargs
