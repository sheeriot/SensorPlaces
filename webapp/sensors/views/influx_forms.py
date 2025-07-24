from django import forms
from django.urls import reverse
from ..models import InfluxSource, Place
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, HTML

class InfluxSourceForm(forms.ModelForm):
    place = forms.ModelChoiceField(queryset=Place.objects.all(), widget=forms.HiddenInput())

    class Meta:
        model = InfluxSource
        fields = ["name", "url", "org", "bucket_name", "token", "place"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'url',
            'org',
            'bucket_name',
            'token',
            'place',
            HTML('<hr>'),
            Submit('submit', 'Save', css_class='btn btn-primary'),
            HTML('<a class="btn btn-secondary" href="{% url \'sensors:influxsource_list\' place_slug=view.place.slug %}">Cancel</a>')
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