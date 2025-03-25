from django import forms
from django.db import models
from django.utils.safestring import mark_safe
from ..models import Device

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML, Div


from icecream import ic


class DeviceForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Device
        fields = ['name', 'is_active', 'location', 'device_type', 'manufacturer', 'model', 'serial_number']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter device name'}),
            'manufacturer': forms.TextInput(attrs={'placeholder': 'Enter manufacturer'}),
            'model': forms.TextInput(attrs={'placeholder': 'Enter model'}),
            'serial_number': forms.TextInput(attrs={'placeholder': 'Enter serial number'}),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input active-checkbox',
                'data-active-label': 'Active',
                'data-inactive-label': 'inactive',
                'style': 'margin-top: 0.1rem;'
            })
        }

    def __init__(self, *args, **kwargs):
        # Pop parameters from FormDataMixin that we don't use
        self.place = kwargs.pop('place', None)
        self.locations = kwargs.pop('locations', None)
        self.location = kwargs.pop('location', None)
        self.devices_active = kwargs.pop('devices_active', None)
        inactive_help_text = kwargs.pop('inactive_help_text', None)
        super().__init__(*args, **kwargs)
        
        # Configure crispy form helper
        self.helper = FormHelper()
        self.helper.form_id = 'device-form'
        self.helper.form_class = 'model-form'

        # Setup Active field with proper ID and label
        checkbox_id = f"device-active-checkbox-{self.instance.pk if self.instance and self.instance.pk else 'new'}"
        self.fields['is_active'].widget.attrs.update({
            'id': checkbox_id,
            'data-device-id': str(self.instance.pk) if self.instance and self.instance.pk else 'new',
        })
        
        # Set the initial label based on current state
        if self.instance and self.instance.pk and not self.instance.is_active:
            self.fields['is_active'].label = 'inactive'
            self.fields['is_active'].widget.attrs['data-inactive-label'] = 'inactive'
            self.fields['is_active'].widget.attrs['data-active-label'] = 'Active'
        else:
            self.fields['is_active'].label = 'Active'
            self.fields['is_active'].widget.attrs['data-inactive-label'] = 'inactive'
            self.fields['is_active'].widget.attrs['data-active-label'] = 'Active'
        
        # Store original state for JavaScript
        if self.instance and self.instance.pk:
            self.fields['is_active'].widget.attrs['data-isactive-original'] = str(self.instance.is_active).lower()
            if self.instance.location:
                self.fields['is_active'].widget.attrs['data-location-original'] = str(self.instance.location.pk)
                
                # If location is inactive, device must be inactive
                if not self.instance.location.is_active:
                    self.fields['is_active'].initial = False
                    self.fields['is_active'].widget.attrs['disabled'] = True
                    self.fields['is_active'].label = 'inactive'
                    
                    # Set help text for inactive state
                    self.fields['is_active'].help_text = mark_safe(
                        f'<i class="bi bi-exclamation-triangle me-2"></i>'
                        f'Device cannot be active because Location "{self.instance.location.name}" is inactive.'
                    )
                    
        # Apply inactive_help_text if provided from view
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

        # Handle initial location if provided
        initial = kwargs.get('initial', {})
        location_initial = initial.get('location', None) or self.location
        if location_initial:
            self.location = location_initial  # Set the form's location            
            # Handle location-based activation constraints
            if not location_initial.is_active:
                self.fields['is_active'].initial = False
                self.fields['is_active'].widget.attrs['disabled'] = True
                self.fields['is_active'].label = 'inactive'
                
                # Only set help text if not already provided from view
                if not inactive_help_text:
                    self.fields['is_active'].help_text = mark_safe(
                        f'<i class="bi bi-exclamation-triangle me-2"></i>'
                        f'Device cannot be active because Location "{location_initial.name}" is inactive.'
                    )
                    
        """Configure the location select field with active state and device counts"""
        if self.locations:
            # Build location choices with status indicators
            choices = [('', '---------')]
            for location in self.locations:
                if location.is_active:
                    label = f"{location.name} ({location.devices_active_count} active)"
                else:
                    label = f"{location.name} (inactive)"
                choices.append((location.pk, label))            
            # Configure the select widget with data attributes for active states
            select_attrs = {
                'class': 'form-select',
                'id': 'id_location',  # Ensure consistent ID
            }
            # Add data attributes for each location
            for loc in self.locations:
                select_attrs[f'data-isactive-{loc.pk}'] = str(loc.is_active).lower()
                select_attrs[f'data-locationname-{loc.pk}'] = loc.name
            # Update the location field
            self.fields['location'].queryset = self.locations
            self.fields['location'].widget = forms.Select(
                attrs=select_attrs,
                choices=choices
            )

        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-12'),
                css_class='mb-2'
            ),
            Row(
                Column(
                    Field(
                        'is_active',
                        template='sensors/partials/active_status_checkbox.html',
                        model_name='device',
                        instance_pk=self.instance.pk if self.instance and self.instance.pk else 'new',
                        css_id='div_id_is_active'
                    ),
                    css_class='col-12'
                ),
                css_class='mb-2'
            ),
            Row(
                Column('device_type', css_class='col-4'),
                css_class='mb-2'
            ),
            Row(
                Column('location', css_class='col-4', css_id='div_id_location'),
                css_class='mb-2'
            ),
            Row(
                Column('manufacturer', css_class='col-auto'),
                Column('model', css_class='col-auto'),
                css_class='mb-1'
            ),
            Row(
                Column('serial_number', css_class='col-auto'),
                css_class='mb-2'
            ),
            Div(
                HTML('<hr class="mt-1">'),
                Div(
                    Field('referrer', type='hidden'),
                    HTML(f"""
                        <a href="{{ form.referrer.value|default:cancel_fallback_url }}" 
                           class="btn btn-outline-secondary">
                            <i class="bi bi-x-lg me-1"></i>Cancel
                        </a>
                    """),
                    HTML("""
                        <button type="submit" class="btn btn-success">
                            <i class="bi bi-hdd-rack me-1"></i>{% if not object %}Create{% else %}Save{% endif %}
                        </button>
                    """),
                    css_class='d-flex justify-content-between align-items-center'
                ),
                css_class='mt-3'
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        location = cleaned_data.get('location') or self.location
        
        # Ensure location is set
        if not location and self.location:
            cleaned_data['location'] = self.location
            self.instance.location = self.location
        
        # Check for duplicate device names in the same place
        if name and location:
            # Get the place from the location
            place = location.place
            
            # Check for duplicates in the same place
            duplicate_query = Device.objects.filter(
                location__place=place,
                name__iexact=name
            )
            
            # Exclude self when checking for duplicates
            if self.instance and self.instance.pk:
                duplicate_query = duplicate_query.exclude(pk=self.instance.pk)
            
            duplicate = duplicate_query.first()
            
            if duplicate:
                self.add_error('name', (
                    f"A device named '{name}' already exists in this place "
                    f"(in location '{duplicate.location.name if duplicate.location else 'Unknown'}')."
                    f"Please choose a different name."
                ))
        
        # Enforce that device must be inactive if location is inactive
        if location and not location.is_active and cleaned_data.get('is_active', False):
            cleaned_data['is_active'] = False
            self.add_error('is_active', "Device cannot be active when its location is inactive.")
        
        return cleaned_data

    def clean_serial_number(self):
        serial_number = self.cleaned_data.get('serial_number')
        manufacturer = self.cleaned_data.get('manufacturer')
        model = self.cleaned_data.get('model')

        if serial_number:
            # Get existing devices with the same serial number, excluding current device if editing
            existing_devices = Device.objects.filter(serial_number=serial_number)
            if self.instance and self.instance.pk:
                existing_devices = existing_devices.exclude(pk=self.instance.pk)

            if existing_devices.exists():
                # Check if any device with same serial number has matching manufacturer or model
                matching_devices = existing_devices.filter(
                    models.Q(manufacturer=manufacturer) | models.Q(model=model)
                )

                if matching_devices.exists():
                    raise forms.ValidationError(
                        "A device with this serial number already exists with the same manufacturer or model."
                    )
                else:
                    self.add_warning(
                        'serial_number',
                        'This serial number is already in use by another device.'
                    )

        return serial_number

    def add_warning(self, field, message):
        if not hasattr(self, '_warnings'):
            self._warnings = {}
        if field not in self._warnings:
            self._warnings[field] = []
        self._warnings[field].append(message)

    def get_warnings(self):
        return getattr(self, '_warnings', {})
