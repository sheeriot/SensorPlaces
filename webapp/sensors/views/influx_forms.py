from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from ..models import InfluxStore, Place
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, HTML, Div
from crispy_forms.bootstrap import FormActions


class InfluxStoreForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput, required=False)
    cancel_url = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = InfluxStore
        fields = ['name', 'url', 'org', 'bucket_name', 'token', 'place']
        widgets = {
            'place': forms.HiddenInput(),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'url': forms.TextInput(attrs={'class': 'form-control'}),
            'org': forms.TextInput(attrs={'class': 'form-control'}),
            'bucket_name': forms.TextInput(attrs={'class': 'form-control'}),
            'token': forms.PasswordInput(render_value=True, attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        cancel_url = kwargs.pop('cancel_url', None)

        super().__init__(*args, **kwargs)

        self.helper.layout = Layout(
            'name',
            'url',
            'org',
            'bucket_name',
            'token',
            'place',
            Div(
                HTML(f'<a href="{cancel_url}" class="btn btn-outline-secondary">Cancel</a>'),
                Submit('submit', 'Save InfluxStore', css_class='btn btn-primary'),
                css_class='mt-3 d-flex justify-content-end gap-2'
            )
        )

        self.fields['name'].label = "Store Name"
        self.fields['token'].label = "Access Token"
        self.fields['token'].widget.attrs['placeholder'] = 'Leave blank to keep unchanged'
        self.fields['token'].required = False
        
        if self.instance and self.instance.token:
            self.initial['token'] = ''

    def get_help_text(self, field_name):
        help_texts = {
            'name': 'A descriptive name for this InfluxDB connection.',
            'url': 'The base URL of your InfluxDB instance (e.g., http://localhost:8086).',
            'org': 'The name of your InfluxDB organization.',
            'bucket_name': 'The name of the bucket to store data in.',
            'token': 'Your InfluxDB API token with write permissions.',
        }
        return help_texts.get(field_name, '')

    def clean_name(self):
        name = self.cleaned_data.get('name')
        place = self.cleaned_data.get('place')
        instance = self.instance

        if name and place:
            queryset = InfluxStore.objects.filter(place=place, name__iexact=name)
            if instance and instance.pk:
                queryset = queryset.exclude(pk=instance.pk)
            if queryset.exists():
                raise ValidationError("An InfluxDB store with this name already exists for this place.")
        return name

    def clean_token(self):
        # If the token field is left blank, keep the existing one.
        token = self.cleaned_data.get('token')
        if not token and self.instance and self.instance.pk:
            return self.instance.token
        return token

    def clean(self):
        cleaned_data = super().clean()
        # If the token field is left blank, don't update it.
        if not cleaned_data.get('token') and self.instance and self.instance.token:
            cleaned_data['token'] = self.instance.token
        return cleaned_data
