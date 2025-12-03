from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Submit
from crispy_forms.bootstrap import FormActions

from ..models import SensorType


class SensorTypeForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = SensorType
        fields = [
            'name', 'description', 'unit', 'graph_type',
            'min_value', 'max_value', 'allow_override', 'decimal_places'
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
                Column('unit', css_class='form-group col-md-6 mb-0'),
                Column('graph_type', css_class='form-group col-md-6 mb-0'),
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
                HTML(f'<a href="{cancel_url}" class="btn btn-secondary"><i class="bi bi-x-circle"></i> Cancel</a>')
            )
        )

        # Add icon to submit button
        self.helper.layout[-1].fields[0] = Submit('submit', 'Save', css_class='btn-primary')
        # We can't easily inject HTML into Submit object, but we can use HTML for the button or customize the template.
        # However, Crispy's Submit button renders as <input type="submit"> usually, which doesn't support HTML content easily unless we use <button>.
        # Better approach: Use HTML button for save too?
        # Or standard crispy Submit with css class?
        # Wait, the user asked for "decorate ... buttons with ... icons (i bi)".

        # Let's try replacing the Submit object with a BUTTON object or HTML.
        # <button type="submit" ...><i ...></i> Save</button>

        self.helper.layout.fields[-1] = FormActions(
            HTML('<button type="submit" name="submit" class="btn btn-primary"><i class="bi bi-save"></i> Save</button>'),
            HTML(f'<a href="{cancel_url}" class="btn btn-secondary ms-2"><i class="bi bi-x-circle"></i> Cancel</a>')
        )
