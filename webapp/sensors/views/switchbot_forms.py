# webapp/sensors/views/switchbot_forms.py
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Div
from django.urls import reverse
from django.forms import ModelForm
from ..models import Place, InfluxStore


class SwitchBotConfigForm(ModelForm):
    class Meta:
        model = Place
        fields = [
            'switchbot_user_id',
            'switchbot_token',
            'switchbot_secret',
        ]
        widgets = {
            'switchbot_token': forms.TextInput(attrs={'class': 'form-control font-monospace', 'autocomplete': 'off'}),
            'switchbot_user_id': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'switchbot_user_id': 'SwitchBot User ID',
            'switchbot_token': 'SwitchBot API Token',
            'switchbot_secret': 'SwitchBot API Secret',
        }

    def __init__(self, *args, **kwargs):
        place = kwargs.pop('place', None)
        super().__init__(*args, **kwargs)

        self.fields['switchbot_user_id'].help_text = "For documentation. Not used by the app."

        # Configure token field
        self.fields['switchbot_token'].required = False
        self.fields['switchbot_token'].widget.attrs['placeholder'] = 'Leave blank to keep unchanged'
        
        self.fields['switchbot_secret'].widget = forms.PasswordInput(attrs={'class': 'form-control font-monospace', 'placeholder': 'Leave blank to keep unchanged'}, render_value=False)
        self.fields['switchbot_secret'].required = False
        
        # Pass token/secret status to the template
        self.token_is_set = bool(self.instance and self.instance.switchbot_token)
        self.secret_is_set = bool(self.instance and self.instance.switchbot_secret)

        # Clear initial value so full token is not displayed in the form
        if self.token_is_set:
            self.initial['switchbot_token'] = ''
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_action = reverse('sensors:switchbot_config_update', kwargs={'place_slug': self.instance.slug})
        self.helper.layout = Layout(
            Div('switchbot_user_id', css_class='mb-3'),
            Div('switchbot_token', css_class='mb-3'),
            Div('switchbot_secret', css_class='mb-3'),
        )

    def clean(self):
        cleaned_data = super().clean()
        # Preserve existing credentials if the form fields are empty
        if self.instance and self.instance.pk:
            if not cleaned_data.get('switchbot_token') and self.instance.switchbot_token:
                cleaned_data['switchbot_token'] = self.instance.switchbot_token
            if not cleaned_data.get('switchbot_secret') and self.instance.switchbot_secret:
                cleaned_data['switchbot_secret'] = self.instance.switchbot_secret
        return cleaned_data


class SwitchBotInfluxStoreForm(ModelForm):
    class Meta:
        model = Place
        fields = ['switchbot_influx_store']
        labels = {
            'switchbot_influx_store': 'InfluxDB Store',
        }

    def __init__(self, *args, **kwargs):
        place = kwargs.pop('place', None)
        super().__init__(*args, **kwargs)

        if place:
            self.fields['switchbot_influx_store'].queryset = InfluxStore.objects.filter(place=place)
        
        self.fields['switchbot_influx_store'].widget.attrs.update({
            'class': 'form-select',
        })
