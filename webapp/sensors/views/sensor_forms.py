from django import forms
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Div, Submit, Field
from crispy_forms.bootstrap import FormActions

from ..models import Sensor

from icecream import ic


class SensorForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Sensor
        fields = ['device', 'name', 'is_active', 'sensor_type', 'unit', 'graph_type', 'data_type', 'influx_source', 'influx_measurement']
        widgets = {
            'device': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input active-checkbox',
                    'data-active-label': 'Active',
                    'data-inactive-label': 'inactive',
                    'style': 'margin-top: 0.1rem;'
                }
            ),
            'sensor_type': forms.Select(attrs={'class': 'form-select'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'graph_type': forms.Select(attrs={'class': 'form-select'}),
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
            self.fields['device'].widget = forms.HiddenInput()
            self.fields['device'].initial = self.device.pk
            
            # If device is inactive, sensor must be inactive
            if not self.device.is_active:
                self.fields['is_active'].initial = False
                self.fields['is_active'].widget.attrs['disabled'] = True
                self.fields['is_active'].label = 'inactive'  # Set initial label
                
                # Set help text for inactive state
                self.fields['is_active'].help_text = mark_safe(
                    f'<i class="bi bi-exclamation-triangle me-2"></i>'
                    f'Sensor cannot be active because Device "{self.device.name}" is inactive.'
                )
        # For existing instance, check if device is inactive
        elif self.instance and self.instance.pk and self.instance.device and not self.instance.device.is_active:
            self.fields['is_active'].initial = False
            self.fields['is_active'].widget.attrs['disabled'] = True
            self.fields['is_active'].label = 'inactive'  # Set initial label
            
            # Set help text for inactive state
            self.fields['is_active'].help_text = mark_safe(
                f'<i class="bi bi-exclamation-triangle me-2"></i>'
                f'Sensor cannot be active because Device "{self.instance.device.name}" is inactive.'
            )
        # For existing instances that are inactive for other reasons
        elif self.instance and self.instance.pk and not self.instance.is_active:
            self.fields['is_active'].label = 'Inactive'
        else:
            self.fields['is_active'].label = 'Active'  # Set initial label
            
        # Apply inactive_help_text if provided
        if inactive_help_text:
            self.fields['is_active'].help_text = inactive_help_text

        # Setup Active field with proper ID
        checkbox_id = f"sensor-active-checkbox-{self.instance.pk if self.instance and self.instance.pk else 'new'}"
        self.fields['is_active'].widget.attrs.update({
            'id': checkbox_id,
            'data-sensor-id': str(self.instance.pk) if self.instance and self.instance.pk else 'new'
        })

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
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            # Hidden fields
            'referrer',
            'device',
            # Main fields
            Row(
                Column('name', css_class='form-group col-md-6'),
                Column(
                    HTML("""
                        <div class="form-group">
                            <label for="id_device_name">Device</label>
                            <div id="id_device_name" class="form-control-plaintext">
                                <i class="bi bi-hdd-rack me-2"></i>{{ device }}
                            </div>
                        </div>
                    """),
                    css_class='form-group col-md-6'
                ),
                css_class='form-row'
            ),
            Row(
                Column(
                    'is_active',
                    css_class='form-group col-md-12'
                ),
                css_class='form-row'
            ),
            Row(
                Column('sensor_type', css_class='form-group col-md-4'),
                Column('unit', css_class='form-group col-md-4'),
                Column('graph_type', css_class='form-group col-md-4'),
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
                style='display:none;' if not self.instance.data_type == 'INFLUX' else ''
            ),
            FormActions(
                Submit('submit', 'Save' if self.instance.pk else 'Create', css_class='btn-primary'),
                HTML('<a href="{{ referrer|default:cancel_url }}" class="btn btn-secondary">Cancel</a>'),
            )
        )

        if not self.instance.pk:
            self.helper.layout[-1][0].field_classes += ' bi bi-thermometer-plus'

    def clean(self):
        cleaned_data = super().clean()
        data_type = cleaned_data.get('data_type')
        device = cleaned_data.get('device') or self.device
        influx_source = cleaned_data.get('influx_source')
        influx_measurement = cleaned_data.get('influx_measurement')

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


class LoRaWANSensorForm(forms.ModelForm):
    class Meta:
        model = Sensor
        fields = ['name', 'is_active', 'sensor_type', 'influx_source', 'influx_measurement']

    def __init__(self, *args, **kwargs):
        place = kwargs.pop('place', None)
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = "Active"
        self.fields['influx_source'].label = False
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-8'),
                Column('is_active', css_class='col-4 pt-4'),
            ),
            'sensor_type',
            Div(
                HTML("""
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <label for="id_influx_source" class="form-label mb-0">Influx source</label>
                        <a href="{% url 'sensors:influxsource_create' place_slug=view.place.slug %}"
                           class="btn btn-sm btn-outline-primary" 
                           id="add-influx-source-btn">
                            <i class="bi bi-plus-circle"></i> Source
                        </a>
                    </div>
                """),
                Field('influx_source'),
                css_class="mb-3"
            ),
            'influx_measurement',
            HTML('<hr>'),
            HTML('<button type="submit" class="btn btn-primary">Save</button>'),
            HTML('<a class="btn btn-secondary" href="{{ request.META.HTTP_REFERER }}">Cancel</a>')
        )
