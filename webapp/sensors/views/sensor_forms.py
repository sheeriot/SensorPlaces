from django import forms
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Div, Submit  # TemplateNameMixin
from crispy_forms.bootstrap import FormActions

from ..models import Sensor

from icecream import ic


class SensorForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Sensor
        fields = ['device', 'name', 'is_active', 'sensor_type', 'unit', 'data_type', 'influx_source', 'influx_measurement']
        widgets = {
            'device': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'sensor_type': forms.Select(attrs={'class': 'form-select'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'data_type': forms.Select(attrs={'class': 'form-select'}),
            'influx_source': forms.Select(attrs={'class': 'form-select'}),
            'influx_measurement': forms.TextInput(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        # Handle all possible parameters from views/mixins
        self.device = kwargs.pop('device', None)
        self.place = kwargs.pop('place', None)
        # Make sure to pop these parameters even if we don't use them
        inactive_help_text = kwargs.pop('inactive_help_text', None)
        kwargs.pop('locations', None)
        kwargs.pop('devices_active', None)
        
        super().__init__(*args, **kwargs)

        # Set default device if provided
        if self.device:
            self.fields['device'].initial = self.device
            
            # If device is inactive, sensor must be inactive
            if not self.device.is_active:
                self.fields['is_active'].initial = False
                self.fields['is_active'].widget.attrs['disabled'] = True
                self.fields['is_active'].label = 'inactive'
                
                # Set help text for inactive state
                self.fields['is_active'].help_text = mark_safe(
                    f'<i class="bi bi-exclamation-triangle me-2"></i>'
                    f'Sensor cannot be active because Device "{self.device.name}" is inactive.'
                )
        # For existing instance, check if device is inactive
        elif self.instance and self.instance.pk and self.instance.device and not self.instance.device.is_active:
            self.fields['is_active'].initial = False
            self.fields['is_active'].widget.attrs['disabled'] = True
            self.fields['is_active'].label = 'inactive'
            
            # Set help text for inactive state
            self.fields['is_active'].help_text = mark_safe(
                f'<i class="bi bi-exclamation-triangle me-2"></i>'
                f'Sensor cannot be active because Device "{self.instance.device.name}" is inactive.'
            )
        # For existing instances that are inactive for other reasons
        elif self.instance and self.instance.pk and not self.instance.is_active:
            self.fields['is_active'].label = 'inactive'
        else:
            self.fields['is_active'].label = 'Active'
            
        # Apply inactive_help_text if provided
        if inactive_help_text:
            self.fields['is_active'].help_text = inactive_help_text

        # If we have data_type, update fields based on it
        if 'data_type' in self.data:
            data_type = self.data.get('data_type')
            if data_type == 'INFLUX':
                self.fields['influx_source'].required = True
                self.fields['influx_measurement'].required = True
            else:
                self.fields['influx_source'].required = False
                self.fields['influx_measurement'].required = False
        else:
            # Set defaults for new instances
            self.fields['influx_source'].required = False
            self.fields['influx_measurement'].required = False

        # Add form helpers
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            # Hidden field
            'referrer',
            # Main fields
            Row(
                Column('name', css_class='form-group col-md-6'),
                Column('device', css_class='form-group col-md-6'),
                css_class='form-row'
            ),
            Row(
                Column('is_active', css_class='form-group col-md-6'),
                css_class='form-row'
            ),
            Row(
                Column('sensor_type', css_class='form-group col-md-6'),
                Column('unit', css_class='form-group col-md-6'),
                css_class='form-row'
            ),
            Row(
                Column('data_type', css_class='form-group col-md-12'),
                css_class='form-row'
            ),
            Div(
                Row(
                    Column('influx_source', css_class='form-group col-md-6'),
                    Column('influx_measurement', css_class='form-group col-md-6'),
                    css_class='form-row'
                ),
                css_class='influx-fields',
                # Hide by default until data_type is set
                style='display:none;'
            ),
            FormActions(
                Submit('submit', 'Save', css_class='btn-primary'),
                HTML('<a href="{% if referrer %}{{ referrer }}{% else %}{% url "sensors:place_detail" place_slug=place.slug %}{% endif %}" class="btn btn-secondary">Cancel</a>'),
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        data_type = cleaned_data.get('data_type')
        influx_source = cleaned_data.get('influx_source')
        influx_measurement = cleaned_data.get('influx_measurement')
        device = cleaned_data.get('device') or self.device

        # Ensure device is set
        if not device and self.device:
            cleaned_data['device'] = self.device
            self.instance.device = self.device

        # Validate device is provided
        if not device:
            raise forms.ValidationError("Device is required")

        # Enforce that sensor must be inactive if device is inactive
        if device and not device.is_active and cleaned_data.get('is_active', False):
            cleaned_data['is_active'] = False
            self.add_error('is_active', "Sensor cannot be active when its device is inactive.")
            
        # Additionally check if the device's location is inactive
        if device and device.location and not device.location.is_active and cleaned_data.get('is_active', False):
            cleaned_data['is_active'] = False
            self.add_error('is_active', "Sensor cannot be active when its device's location is inactive.")

        # Validate InfluxDB fields if data type is INFLUX
        if data_type == 'INFLUX':
            if not influx_source:
                self.add_error('influx_source', "InfluxDB source is required when data type is InfluxDB")
            if not influx_measurement:
                self.add_error('influx_measurement', "InfluxDB measurement is required when data type is InfluxDB")

        return cleaned_data

    def is_valid(self):
        # Ensure device is set on the instance before validation
        if hasattr(self, 'device') and self.device and not self.instance.device_id:
            self.instance.device = self.device
        return super().is_valid()
