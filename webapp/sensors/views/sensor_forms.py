from django import forms
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Div, Submit, Field
from crispy_forms.bootstrap import FormActions

from ..models import Sensor, SensorType


class SensorTypeSelect(forms.Select):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Defer the queryset until the form is rendering
        self.sensor_types_cache = None

    def _load_cache(self):
        if self.sensor_types_cache is None:
            try:
                self.sensor_types_cache = {
                    st.pk: st for st in SensorType.objects.select_related('default_unit').all()
                }
            except Exception:
                # If the database isn't ready (e.g., during migrations), fail gracefully
                self.sensor_types_cache = {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        # Load cache just in time
        if self.sensor_types_cache is None:
            self._load_cache()

        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value and self.sensor_types_cache and value in self.sensor_types_cache:
            sensor_type = self.sensor_types_cache[value]
            option['attrs']['data-default-unit-id'] = sensor_type.default_unit.id if sensor_type.default_unit else ''
            # option['attrs']['data-default-data-type'] = sensor_type.default_data_type or '' # Removed as default_data_type is no longer in SensorType
            option['attrs']['data-min-value'] = str(sensor_type.min_value) if sensor_type.min_value is not None else ''
            option['attrs']['data-max-value'] = str(sensor_type.max_value) if sensor_type.max_value is not None else ''
        return option


class SensorForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Sensor
        fields = [
            'device', 'name', 'is_active', 'sensor_type',
            'unit', 'unit_override',
            'data_type',
            'min_value', 'min_value_override',
            'max_value', 'max_value_override',
            'graph_type',
            'influx_source', 'influx_measurement'
        ]
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
            'sensor_type': SensorTypeSelect(attrs={'class': 'form-select'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'unit_override': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'graph_type': forms.Select(attrs={'class': 'form-select'}),
            'data_type': forms.Select(attrs={'class': 'form-select'}),
            'min_value': forms.NumberInput(attrs={'class': 'form-control'}),
            'min_value_override': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_value': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_value_override': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'influx_source': forms.Select(attrs={'class': 'form-select'}),
            'influx_measurement': forms.TextInput(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        # Handle all possible parameters from views/mixins
        self.device = kwargs.pop('device', None)
        self.place = kwargs.pop('place', None)
        self.cancel_url = kwargs.pop('cancel_url', None)
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

        self.fields['name'].label = "Sensor Name"
        self.fields['sensor_type'].label = "Sensor Type"
        self.fields['graph_type'].label = "Graph Type"

        self.fields['unit'].label = False
        self.fields['data_type'].label = False
        self.fields['min_value'].label = False
        self.fields['max_value'].label = False

        # Set the initial value for the unit field from the effective_unit
        if self.instance and self.instance.pk:
            self.fields['unit'].initial = self.instance.effective_unit.pk if self.instance.effective_unit else None

        # Apply inactive_help_text if provided
        if inactive_help_text:
            self.fields['is_active'].help_text = inactive_help_text

        # Setup Active field with proper ID
        checkbox_id = f"sensor-active-checkbox-{self.instance.pk if self.instance and self.instance.pk else 'new'}"
        self.fields['is_active'].widget.attrs.update({
            'id': checkbox_id,
            'data-sensor-id': str(self.instance.pk) if self.instance and self.instance.pk else 'new'
        })

        # Pre-populate the form with effective values if they are not overridden.
        # This ensures the form displays the default from the SensorType.
        if self.instance and self.instance.pk:
            if not self.instance.unit_override:
                self.initial['unit'] = self.instance.effective_unit.pk if self.instance.effective_unit else None
            self.initial['data_type'] = self.instance.effective_data_type

        # Set labels for the override fields and remove help text for cleaner layout
        self.fields['unit_override'].label = "Override"
        self.fields['unit_override'].help_text = None
        self.fields['min_value_override'].label = "Override"
        self.fields['max_value_override'].label = "Override"
        self.fields['min_value_override'].help_text = None
        self.fields['max_value_override'].help_text = None

        # --- New logic for allow_override ---
        # Get the selected SensorType instance
        sensor_type = None
        if self.instance and self.instance.sensor_type:
            sensor_type = self.instance.sensor_type

        # If a sensor type is selected, check its allow_override flag
        if sensor_type and not sensor_type.allow_override:
            # Disable override fields if not allowed
            self.fields['unit'].disabled = True
            self.fields['unit_override'].disabled = True
            # data_type is now always editable or controlled by other means,
            # but since we removed the override flag, we just let it be.
            # Or should we disable data_type dropdown if allow_override is false?
            # The user asked to remove data_type_override logic.
            pass
        else:
            pass
        # --- End of new logic ---

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
            'referrer',
            'device',
            Row(
                Column('name', css_class='form-group col-md-9 mb-0'),
                Column(Field('is_active', wrapper_class='form-check form-switch mt-4'), css_class='form-group col-md-3 mb-0'),
                css_class='form-row align-items-center'
            ),
            Row(
                Column('sensor_type', css_class='form-group col-md-auto mb-0'),
                Column('graph_type', css_class='form-group col-md-auto mb-0')
            ),
            HTML('<hr class="my-3">'),
            Row(
                Column(
                    Div(
                        HTML('<label for="id_unit" class="form-label mb-0">Unit</label>'),
                        Field('unit_override', wrapper_class='form-check form-switch'),
                        css_class='d-flex justify-content-between align-items-baseline'
                    ),
                    Div(Field('unit', id="id_unit"), css_class="mb-1"),
                    css_class='form-group col-md-auto mb-0'
                ),
                Column(
                    Div(
                        HTML('<label for="id_data_type" class="form-label mb-0">Data Type</label>'),
                        # Removed data_type_override field
                        css_class='d-flex justify-content-between align-items-baseline'
                    ),
                    Div(Field('data_type', id="id_data_type"), css_class="mb-1"),
                    css_class='form-group col-md-auto mb-0'
                ),
                Column(
                    Div(
                        HTML('<label for="id_min_value" class="form-label mb-0">Min Value</label>'),
                        Field('min_value_override', wrapper_class='form-check form-switch'),
                        css_class='d-flex justify-content-between align-items-baseline'
                    ),
                    Div(Field('min_value', id="id_min_value"), css_class="mb-1"),
                    css_class='form-group col-md-auto mb-0'
                ),
                Column(
                    Div(
                        HTML('<label for="id_max_value" class="form-label mb-0">Max Value</label>'),
                        Field('max_value_override', wrapper_class='form-check form-switch'),
                        css_class='d-flex justify-content-between align-items-baseline'
                    ),
                    Div(Field('max_value', id="id_max_value"), css_class="mb-1"),
                    css_class='form-group col-md-auto mb-0'
                )
            ),
            Div(
                HTML('<hr class="my-3">'),
                css_class='w-100'
            ),
            Div(
                Row(
                    Column(
                        Field('influx_source'),
                        css_class="form-group col-md-6 mb-0"
                    ),
                    Column('influx_measurement', css_class='form-group col-md-6 mb-0'),
                ),
                id='influx-fields'
            ),
            HTML('<hr class="my-3">'),
            Div(
                FormActions(
                    HTML(f'<a role="button" href="{self.cancel_url}" class="btn btn-secondary me-2"><i class="bi bi-x-circle"></i> Cancel</a>'),
                    HTML(f'<button type="submit" class="btn btn-success"><i class="bi bi-check-circle"></i> {"Save" if self.instance.pk else "Create"}</button>')
                ),
                css_class='d-flex justify-content-end'
            )
        )

        if not self.instance.pk:
            # Note: This might need adjustment if the layout changes significantly
            try:
                self.helper.layout.fields[-1].fields[1].html = f'<button type="submit" class="btn btn-success"><i class="bi bi-plus-circle"></i> Create</button>'
            except (AttributeError, IndexError):
                pass # Fail silently if layout is not as expected

    def clean(self):
        cleaned_data = super().clean()
        data_type = cleaned_data.get('data_type')
        device = cleaned_data.get('device') or self.device
        influx_source = cleaned_data.get('influx_source')
        influx_measurement = cleaned_data.get('influx_measurement')
        unit_override = cleaned_data.get('unit_override')
        min_value_override = cleaned_data.get('min_value_override')
        max_value_override = cleaned_data.get('max_value_override')

        # If a sensor type is selected, enforce override logic
        sensor_type = cleaned_data.get('sensor_type')
        if sensor_type:
            # If unit override is selected but matches the default, clear it
            if unit_override and cleaned_data.get('unit') == sensor_type.default_unit:
                cleaned_data['unit'] = None
                cleaned_data['unit_override'] = False

            # If min value override is selected but matches the default, clear it
            if min_value_override and cleaned_data.get('min_value') == sensor_type.min_value:
                cleaned_data['min_value'] = None
                cleaned_data['min_value_override'] = False

            # If max value override is selected but matches the default, clear it
            if max_value_override and cleaned_data.get('max_value') == sensor_type.max_value:
                cleaned_data['max_value'] = None
                cleaned_data['max_value_override'] = False

        # --- New override logic ---
        if unit_override and not cleaned_data.get('unit'):
            self.add_error('unit', "Unit must be specified when overriding.")

        # Clear values if not overriding to fall back to SensorType defaults
        if not unit_override:
            cleaned_data['unit'] = None

        if not min_value_override:
            cleaned_data['min_value'] = None
        if not max_value_override:
            cleaned_data['max_value'] = None
        # --- End of new logic ---

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
        cancel_url = kwargs.pop('cancel_url', None)
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
            HTML(f'<a class="btn btn-secondary" href="{cancel_url}">Cancel</a>')
        )
