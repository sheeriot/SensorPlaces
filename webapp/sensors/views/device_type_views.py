from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import DeviceType
from ..forms.device_type_forms import DeviceTypeForm
from .mixins import ReferrerMixin

class DeviceTypeListView(LoginRequiredMixin, ListView):
    model = DeviceType
    template_name = 'sensors/devicetype_list.html'

class DeviceTypeDetailView(LoginRequiredMixin, DetailView):
    model = DeviceType
    template_name = 'sensors/devicetype_detail.html'

class DeviceTypeCreateView(LoginRequiredMixin, ReferrerMixin, CreateView):
    model = DeviceType
    form_class = DeviceTypeForm
    template_name = 'sensors/devicetype_form.html'

    def get_cancel_url(self):
        return reverse('sensors:devicetype_list')

class DeviceTypeUpdateView(LoginRequiredMixin, ReferrerMixin, UpdateView):
    model = DeviceType
    form_class = DeviceTypeForm
    template_name = 'sensors/devicetype_form.html'

    def get_cancel_url(self):
        if hasattr(self, 'object') and self.object:
            return self.object.get_absolute_url()
        return reverse('sensors:devicetype_list')
