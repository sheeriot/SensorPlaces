from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Submit
from crispy_forms.bootstrap import FormActions

from ..models import DeviceType


class DeviceTypeForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = DeviceType
        fields = [
            'name', 'description', 'icon', 'is_active'
        ]

    def __init__(self, *args, **kwargs):
        cancel_url = kwargs.pop('cancel_url', '/')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'referrer',
            'name',
            'description',
            Row(
                Column('icon', css_class='form-group col-md-6 mb-0'),
                Column('is_active', css_class='form-group col-md-6 mb-0'),
            ),
            HTML('<hr>'),
            FormActions(
                HTML('<button type="submit" name="submit" class="btn btn-primary"><i class="bi bi-save"></i> Save</button>'),
                HTML(f'<a href="{cancel_url}" class="btn btn-secondary ms-2"><i class="bi bi-x-circle"></i> Cancel</a>')
            )
        )
