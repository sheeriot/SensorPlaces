from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Submit
from crispy_forms.bootstrap import FormActions

from ..models import SensorType


class SensorTypeForm(forms.ModelForm):
    class Meta:
        model = SensorType
        fields = [
            'name', 'description', 'default_unit', 'default_data_type',
            'min_value', 'max_value', 'allow_override', 'decimal_places'
        ]

    def __init__(self, *args, **kwargs):
        cancel_url = kwargs.pop('cancel_url', '/')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'name',
            'description',
            Row(
                Column('default_unit', css_class='form-group col-md-6 mb-0'),
                Column('default_data_type', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('min_value', css_class='form-group col-md-4 mb-0'),
                Column('max_value', css_class='form-group col-md-4 mb-0'),
                Column('decimal_places', css_class='form-group col-md-4 mb-0'),
            ),
            'allow_override',
            HTML('<hr>'),
            FormActions(
                Submit('submit', 'Save', css_class='btn-primary'),
                HTML(f'<a href="{cancel_url}" class="btn btn-secondary">Cancel</a>')
            )
        )
