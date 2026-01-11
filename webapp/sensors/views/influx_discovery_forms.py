"""
Forms for InfluxDB sensor discovery.
"""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML, Div, Submit
from ..models import InfluxStore


class InfluxStoreSelectionForm(forms.Form):
    """Form for selecting an InfluxStore to discover measurements from."""
    influx_store = forms.ModelChoiceField(
        queryset=InfluxStore.objects.none(),
        label="InfluxDB Store",
        help_text="Select an InfluxDB store to discover measurements from.",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        place = kwargs.pop('place', None)
        super().__init__(*args, **kwargs)

        if place:
            self.fields['influx_store'].queryset = InfluxStore.objects.filter(place=place)

        self.helper = FormHelper()
        self.helper.form_tag = False  # Form tag handled in template
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('influx_store'),
        )


class MeasurementFieldSelectionForm(forms.Form):
    """Form for selecting measurement+field combinations to create sensors."""
    selections = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_id = 'measurement-field-selection-form'
        self.helper.layout = Layout(
            Field('selections'),
            HTML('<div id="selected-items-container"></div>'),
            HTML('<div class="d-flex justify-content-between mt-3">'),
            HTML('<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>'),
            Submit('submit', 'Create Sensors', css_class='btn btn-success'),
            HTML('</div>')
        )
