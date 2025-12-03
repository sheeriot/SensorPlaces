# webapp/sensors/views/switchbot_forms.py
from django import forms
from ..models import Place, InfluxSource

class SwitchBotConfigForm(forms.ModelForm):
    class Meta:
        model = Place
        fields = [
            'switchbot_user_id',
            'switchbot_token',
            'switchbot_secret',
            'switchbot_influx_source'
        ]
        widgets = {
            'switchbot_token': forms.TextInput(attrs={'class': 'form-control font-monospace'}),
            'switchbot_secret': forms.TextInput(attrs={'class': 'form-control font-monospace'}),
            'switchbot_user_id': forms.TextInput(attrs={'class': 'form-control'}),
            'switchbot_influx_source': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'switchbot_user_id': 'SwitchBot User ID',
            'switchbot_token': 'SwitchBot Token',
            'switchbot_secret': 'SwitchBot Secret',
            'switchbot_influx_source': 'SwitchBot InfluxDB Source',
        }

    def __init__(self, *args, **kwargs):
        place = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        # Limit the queryset for the influx source to the current place
        if place:
            self.fields['switchbot_influx_source'].queryset = InfluxSource.objects.filter(place=place)

        self.fields['switchbot_user_id'].help_text = "For documentation. Not used by the app."
