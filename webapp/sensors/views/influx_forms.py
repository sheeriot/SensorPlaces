from django import forms
from django.urls import reverse
from ..models import InfluxSource, Place
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, HTML
from crispy_forms.bootstrap import FormActions

class InfluxSourceForm(forms.ModelForm):
    place = forms.ModelChoiceField(queryset=Place.objects.all(), widget=forms.HiddenInput())
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = InfluxSource
        fields = ["name", "url", "org", "bucket_name", "token", "place"]

    def __init__(self, *args, **kwargs):
        cancel_url = kwargs.pop('cancel_url', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'name',
            'url',
            'org',
            'bucket_name',
            'token',
            'place',
            'referrer',
            HTML('<hr>'),
            FormActions(
                HTML(f'<a class="btn btn-secondary" href="{cancel_url}"><i class="bi bi-x-circle"></i> Cancel</a>'),
                HTML('<button type="submit" class="btn btn-primary"><i class="bi bi-save"></i> Save</button>'),
                css_class="d-flex justify-content-between"
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        place = cleaned_data.get("place")

        if name and place:
            queryset = InfluxSource.objects.filter(place=place, name__iexact=name)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError(
                    "An InfluxDB source with this name already exists for this place."
                )
        return cleaned_data
