from django import forms
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Div, Submit, Field, Fieldset
from crispy_forms.bootstrap import FormActions

from ..models import Sensor, SensorType
from ..models import InfluxStore
from django.urls import reverse
from django.core.exceptions import ValidationError


class SensorTypeSelect(forms.Select):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Defer the queryset until the form is rendering
        self.sensor_types_cache = None

    def _load_cache(self):
        if self.sensor_types_cache is None:
            try:
                self.sensor_types_cache = {
                    st.pk: st for st in SensorType.objects.select_related('unit').all()
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
            option['attrs']['data-unit-id'] = sensor_type.unit.id if sensor_type.unit else ''
            option['attrs']['data-graph-type'] = sensor_type.graph_type or 'LINE'
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

        # Set the initial value for data_type right away
        if self.instance and self.instance.pk:
            self.initial['data_type'] = self.instance.data_type

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

        self.fields['name'].label = False
        self.fields['sensor_type'].label = "Sensor Type"
        self.fields['graph_type'].label = "Graph Type"
        self.fields['data_type'].label = False
        self.fields['unit'].label = False
        self.fields['min_value'].label = False
        self.fields['max_value'].label = False

        self.fields['is_active'].label = False
        self.fields['unit_override'].label = False
        self.fields['min_value_override'].label = False
        self.fields['max_value_override'].label = False

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
            self.initial['data_type'] = self.instance.data_type

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

        # Add form helpers
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'referrer',
            'device',
            HTML("""
                <div class="row align-items-end mb-2">
                    <div class="col-md-8">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <label for="{{ form.name.id_for_label }}" class="form-label mb-0">Sensor Name*</label>
                            <div class="form-check form-switch">
                                {{ form.is_active }}
                                <label class="form-check-label" for="{{ form.is_active.id_for_label }}">Active</label>
                            </div>
                        </div>
                        {{ form.name }}
                    </div>
                    <div class="col-md-4">
                        <label for="{{ form.data_type.id_for_label }}" class="form-label">Data Type</label>
                        {{ form.data_type }}
                    </div>
                </div>
            """),
            Row(
                Column(Field('sensor_type', css_class='w-auto'), css_class='form-group col-md-auto'),
                Column(
                    Field('graph_type'),
                    id="graph_type_container",
                    css_class="form-group col-md-auto d-none"  # Initially hidden
                ),
                css_class="align-items-end mb-2"
            ),
            Div(
                Fieldset(
                    'Unit & Value Configuration',
                    Row(
                        Column(
                            HTML("""
                                <div class="d-flex justify-content-between align-items-center">
                                    <label for="{{ form.unit.id_for_label }}" class="form-label mb-1">Unit</label>
                                    <div class="form-check form-check-reverse">
                                        {{ form.unit_override }}
                                        <label for="{{ form.unit_override.id_for_label }}" class="form-check-label">Override</label>
                                    </div>
                                </div>
                                {{ form.unit }}
                            """),
                            css_class='form-group col-md-4 mb-2'
                        ),
                        Column(
                            HTML("""
                                <div class="d-flex justify-content-between align-items-center">
                                    <label for="{{ form.min_value.id_for_label }}" class="form-label mb-1">Min</label>
                                    <div class="form-check form-check-reverse">
                                        {{ form.min_value_override }}
                                        <label for="{{ form.min_value_override.id_for_label }}" class="form-check-label">Override</label>
                                    </div>
                                </div>
                                {{ form.min_value }}
                            """),
                            css_class='form-group col-md-4 mb-0'
                        ),
                        Column(
                            HTML("""
                                <div class="d-flex justify-content-between align-items-center">
                                    <label for="{{ form.max_value.id_for_label }}" class="form-label mb-1">Max</label>
                                    <div class="form-check form-check-reverse">
                                        {{ form.max_value_override }}
                                        <label for="{{ form.max_value_override.id_for_label }}" class="form-check-label">Override</label>
                                    </div>
                                </div>
                                {{ form.max_value }}
                            """),
                            css_class='form-group col-md-4 mb-0'
                        ),
                    ),
                    css_class="border rounded-3 p-3 mt-2"
                ),
                id="sensor-type-dependent-fields",
                css_class="d-none"
            ),
            Div(
                FormActions(
                    HTML(f'<a role="button" href="{self.cancel_url}" class="btn btn-secondary me-2"><i class="bi bi-x-circle"></i> Cancel</a>'),
                    HTML(f'<button type="submit" class="btn btn-success"><i class="bi bi-save"></i> Save</button>')
                ),
                css_class='d-flex justify-content-end'
            )
        )

        if not self.instance.pk:
            # Note: This might need adjustment if the layout changes significantly
            try:
                self.helper.layout.fields[-1].fields[0].fields[1].html = f'<button type="submit" class="btn btn-success"><i class="bi bi-thermometer"></i> Create Sensor</button>'
            except (AttributeError, IndexError):
                pass # Fail silently if layout is not as expected

    def clean(self):
        cleaned_data = super().clean()
        data_type = cleaned_data.get('data_type')
        device = cleaned_data.get('device') or self.device
        unit_override = cleaned_data.get('unit_override')
        min_value_override = cleaned_data.get('min_value_override')
        max_value_override = cleaned_data.get('max_value_override')

        # If a sensor type is selected, enforce override logic
        sensor_type = cleaned_data.get('sensor_type')
        if sensor_type:
            # If graph_type matches the default, clear it so it's not saved on the instance
            if cleaned_data.get('graph_type') == sensor_type.graph_type:
                cleaned_data['graph_type'] = None

            # If unit is overridden but matches default, treat as not overridden
            if unit_override and cleaned_data.get('unit') == sensor_type.unit:
                cleaned_data['unit_override'] = False
                unit_override = False

            if not unit_override:
                cleaned_data['unit'] = None

            # Handle min_value
            if min_value_override and cleaned_data.get('min_value') == sensor_type.min_value:
                 cleaned_data['min_value_override'] = False
                 min_value_override = False

            if not min_value_override:
                cleaned_data['min_value'] = None

            # Handle max_value
            if max_value_override and cleaned_data.get('max_value') == sensor_type.max_value:
                cleaned_data['max_value_override'] = False
                max_value_override = False

            if not max_value_override:
                cleaned_data['max_value'] = None

        if unit_override and not cleaned_data.get('unit'):
            self.add_error('unit', "Unit must be specified when overriding.")

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

        # If data_type is INFLUX, validate that influx fields are present
        if data_type == 'INFLUX':
            # These fields are not on the form, so we can't add errors to them.
            # The validation should happen on the model or a different form.
            pass

        return cleaned_data

    def is_valid(self):
        # Ensure device is set on the instance before validation
        if hasattr(self, 'device') and self.device and not self.instance.device_id:
            self.instance.device = self.device
        return super().is_valid()


class SensorInfluxUpdateForm(forms.ModelForm):
    class Meta:
        model = Sensor
        fields = ['influx_store', 'influx_measurement', 'influx_field_name', 'influx_tag_key']

    def __init__(self, *args, **kwargs):
        self.place = kwargs.pop('place', None)
        kwargs.pop('cancel_url', None)  # Pop cancel_url to prevent passing to super
        super().__init__(*args, **kwargs)

        if self.place:
            self.fields['influx_store'].queryset = InfluxStore.objects.filter(place=self.place)

        # Use standard labels and add help text
        self.fields['influx_store'].label = "InfluxDB Store"
        self.fields['influx_measurement'].label = "Measurement Name"
        self.fields['influx_field_name'].label = "Field Name"
        self.fields['influx_tag_key'].label = "Tag Key"

        self.fields['influx_tag_key'].help_text = "e.g., host, device_id"

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            'influx_store',
            'influx_measurement',
            'influx_field_name',
            'influx_tag_key',
        )


class LoRaWANSensorForm(forms.ModelForm):
    class Meta:
        model = Sensor
        fields = ['name', 'is_active', 'sensor_type', 'influx_store', 'influx_measurement']

    def __init__(self, *args, **kwargs):
        place = kwargs.pop('place', None)
        cancel_url = kwargs.pop('cancel_url', None)
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = "Active"
        self.fields['influx_store'].label = False
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
                        <label for="id_influx_store" class="form-label mb-0">Influx Store</label>
                        <a href="{% url 'sensors:influxstore_create' place_slug=view.place.slug %}"
                           class="btn btn-sm btn-outline-primary"
                           id="add-influx-store-btn">
                            <i class="bi bi-plus-circle"></i> Store
                        </a>
                    </div>
                """),
                Field('influx_store'),
                css_class="mb-1"
            ),
            'influx_measurement',
            HTML('<hr>'),
            HTML('<button type="submit" class="btn btn-primary">Save</button>'),
            HTML(f'<a class="btn btn-secondary" href="{cancel_url}">Cancel</a>')
        )


class DeviceDeleteForm(forms.Form):
    name_confirm = forms.CharField(
        label="Confirm device name",
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.device_name = kwargs.pop('device_name', None)
        super().__init__(*args, **kwargs)

    def clean_name_confirm(self):
        entered_name = self.cleaned_data.get('name_confirm')
        if entered_name.lower() != self.device_name.lower():
            raise ValidationError("The entered name does not match the device name.")
        return entered_name


class InfluxStoreDeleteForm(forms.Form):
    name_confirm = forms.CharField(
        label="Confirm InfluxDB Store name",
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.store_name = kwargs.pop('store_name', None)
        super().__init__(*args, **kwargs)

    def clean_name_confirm(self):
        entered_name = self.cleaned_data.get('name_confirm')
        if entered_name.lower() != self.store_name.lower():
            raise ValidationError("The entered name does not match the store name.")
        return entered_name
