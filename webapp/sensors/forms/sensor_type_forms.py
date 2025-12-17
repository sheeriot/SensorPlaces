import json
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Fieldset
from crispy_forms.bootstrap import FormActions

from ..models import SensorType


class SensorTypeForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)
    aliases = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_aliases'}),
        help_text="Alternative names that map to this sensor type (for auto-matching)"
    )

    class Meta:
        model = SensorType
        fields = [
            'name', 'description', 'unit', 'graph_type',
            'min_value', 'max_value', 'allow_override', 'decimal_places',
            'default_stale_threshold_seconds', 'influx_measurement', 'influx_field_name'
        ]

    def __init__(self, *args, **kwargs):
        cancel_url = kwargs.pop('cancel_url', '/')
        super().__init__(*args, **kwargs)

        # Initialize aliases field with existing data as JSON
        # Store original for change detection
        original_aliases = []
        if self.instance and self.instance.pk:
            original_aliases = self.instance.aliases or []

        aliases_json = json.dumps(original_aliases)
        self.initial['aliases'] = aliases_json
        self._original_aliases = list(original_aliases)  # Make a copy

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'referrer',
            'name',
            'description',
            Fieldset(
                'Defaults and Overrides',
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
            ),
            Fieldset(
                'Status',
                Row(
                    Column('default_stale_threshold_seconds', css_class='form-group col-md-6 mb-0'),
                ),
            ),
            Fieldset(
                'InfluxDB Configuration',
                Row(
                    Column('influx_measurement', css_class='form-group col-md-6 mb-0'),
                    Column('influx_field_name', css_class='form-group col-md-6 mb-0'),
                ),
            ),
            Fieldset(
                'Matching',
                HTML('''
                    <div class="mb-3">
                        <label class="form-label">Aliases</label>
                        <div class="input-group mb-2">
                            <input type="text" id="alias-input" class="form-control" placeholder="Enter an alias">
                            <button type="button" id="add-alias-btn" class="btn btn-outline-secondary">
                                <i class="bi bi-plus-circle"></i> Add
                            </button>
                        </div>
                        <div id="aliases-container" class="d-flex flex-wrap gap-2 mb-2"></div>
                        <small class="text-muted">Alternative names that map to this sensor type (for auto-matching)</small>
                    </div>
                '''),
                'aliases',
            ),
            HTML('<hr>'),
            FormActions(
                HTML('<button type="submit" name="submit" class="btn btn-primary"><i class="bi bi-save"></i> Save</button>'),
                HTML(f'<a href="{cancel_url}" class="btn btn-secondary ms-2"><i class="bi bi-x-circle"></i> Cancel</a>')
            )
        )

    def clean_aliases(self):
        """Parse the JSON string from the hidden input back to a Python list."""
        aliases_json = self.cleaned_data.get('aliases', '[]')
        if not aliases_json:
            return []
        try:
            aliases_list = json.loads(aliases_json)
            if not isinstance(aliases_list, list):
                return []
            # Ensure all items are strings and strip whitespace
            return [str(alias).strip() for alias in aliases_list if alias]
        except (json.JSONDecodeError, TypeError):
            return []

    def has_changed(self):
        """Check if form has changed, including aliases field."""
        if super().has_changed():
            return True
        # Check if aliases changed
        new_aliases = self.cleaned_data.get('aliases', []) if hasattr(self, 'cleaned_data') else []
        return new_aliases != self._original_aliases

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Only update aliases if changed
        new_aliases = self.cleaned_data.get('aliases', [])
        if new_aliases != self._original_aliases:
            instance.aliases = new_aliases

        if commit:
            if self.instance.pk:
                # Get model field names to filter out non-model fields like 'referrer'
                model_fields = {f.name for f in self._meta.model._meta.get_fields()}
                update_fields = [f for f in self.changed_data if f in model_fields]

                # Add aliases if it changed
                if new_aliases != self._original_aliases:
                    update_fields.append('aliases')

                if update_fields:
                    instance.save(update_fields=update_fields)
                else:
                    instance.save()
            else:
                instance.save()
        return instance
