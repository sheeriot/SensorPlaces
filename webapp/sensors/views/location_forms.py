from django import forms
from django.utils.safestring import mark_safe
from ..models import Location
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML, Div, Submit  # TemplateNameMixin

from icecream import ic


class LocationForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Location
        fields = ['name', 'slug', 'place', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter location name', 'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'placeholder': 'auto-generated from name', 'class': 'form-control'}),
            'place': forms.HiddenInput(),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input active-checkbox',
                'data-active-label': 'Active',
                'data-inactive-label': 'inactive',
                'style': 'margin-top: 0.1rem;'
            })
        }

    def __init__(self, *args, **kwargs):
        # Extract parameters that might be passed but aren't used directly by the form
        self.place = kwargs.pop('place', None)
        inactive_help_text = kwargs.pop('inactive_help_text', None)
        
        # Pop anything that might come from FormDataMixin
        kwargs.pop('locations', None)
        kwargs.pop('devices_active', None)
        super().__init__(*args, **kwargs)
        
        # Setup crispy form helper
        self.helper = FormHelper()
        self.helper.form_id = 'location-form'
        self.helper.form_class = 'model-form'
        
        # Setup Active field with proper ID and label
        checkbox_id = f"location-active-checkbox-{self.instance.pk if self.instance and self.instance.pk else 'new'}"
        self.fields['is_active'].widget.attrs.update({
            'id': checkbox_id,
            'data-location-id': str(self.instance.pk) if self.instance and self.instance.pk else 'new'
        })
        
        # If this is a new location, make slug read-only
        if not self.instance.pk:
            self.fields['slug'].widget.attrs['readonly'] = True
            self.fields['slug'].help_text = 'The slug is auto-generated from the name upon creation.'

        # If we have a place, pre-select it and handle cascading inactive state
        if self.place:
            self.fields['place'].initial = self.place
            
            # If place is inactive, location must be inactive
            if not self.place.is_active:
                self.fields['is_active'].initial = False
                self.fields['is_active'].widget.attrs['disabled'] = True
                self.fields['is_active'].label = 'inactive'  # Set initial label
                
                # Set help text for inactive state
                self.fields['is_active'].help_text = mark_safe(
                    f'<i class="bi bi-exclamation-triangle me-2"></i>'
                    f'Location cannot be active because Place "{self.place.name}" is inactive.'
                )
            else:
                # Set the label based on the instance state
                self.fields['is_active'].label = 'inactive' if (self.instance and self.instance.pk and not self.instance.is_active) else 'Active'
        # Set the label based on the current state for existing instances
        elif self.instance and self.instance.pk:
            self.fields['is_active'].label = 'inactive' if not self.instance.is_active else 'Active'
        else:
            self.fields['is_active'].label = 'Active'
        
        # Set help text for inactive state if provided from view
        if inactive_help_text:
            # Ensure help text doesn't have nested form-text divs
            if '<div class="form-text' in inactive_help_text:
                # Extract the inner content if it's wrapped in a form-text div
                import re
                inner_content = re.search(r'<div class="form-text.*?>(.*?)</div>', inactive_help_text, re.DOTALL)
                if inner_content:
                    self.fields['is_active'].help_text = mark_safe(inner_content.group(1))
                else:
                    self.fields['is_active'].help_text = inactive_help_text
            else:
                self.fields['is_active'].help_text = inactive_help_text
        
        # Form layout with crispy forms
        self.helper.layout = Layout(
            Field('referrer', type='hidden'),
            Field('place', type='hidden'),
            Row(
                Column('name', css_class='col-md-8'),
                Column('slug', css_class='col-md-4'),
                css_class='mb-3'
            ),
            Row(
                Field(
                    'is_active',
                    template='sensors/partials/active_status_checkbox.html',
                    model_name='location',
                    instance_pk=self.instance.pk if self.instance and self.instance.pk else 'new',
                ),
                css_class='mb-3'
            ),
            Div(
                HTML('<hr class="mt-4">'),
                Div(
                    HTML("""
                        <a href="{% if referrer %}{{ referrer }}{% else %}{% url 'sensors:location_list' place_slug=place.slug %}{% endif %}" 
                           class="btn btn-outline-secondary">
                            <i class="bi bi-x-lg me-1"></i>Cancel
                        </a>
                    """),
                    HTML("""
                        <button type="submit" class="btn btn-success">
                            <i class="bi bi-pin-map me-1"></i>{% if not object %}Create{% else %}Save{% endif %}
                        </button>
                    """),
                    css_class='d-flex justify-content-between align-items-center'
                ),
                css_class='mt-3'
            )
        )
        
    def clean(self):
        cleaned_data = super().clean()
        place = cleaned_data.get('place') or self.place
        
        # Ensure place is set
        if not place and self.place:
            cleaned_data['place'] = self.place
            self.instance.place = self.place
        
        # Enforce that location must be inactive if place is inactive
        if place and not place.is_active and cleaned_data.get('is_active', False):
            cleaned_data['is_active'] = False
            self.add_error('is_active', 'Location cannot be active when its place is inactive.')
            
        return cleaned_data
