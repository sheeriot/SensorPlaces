from django import forms
from django.db import models
from django.utils.safestring import mark_safe
from ..models import Device

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML, Div, Submit


from icecream import ic


class DeviceForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Device
        fields = ['name', 'is_active', 'is_lorawan', 'location', 'device_type', 'manufacturer', 'model', 'device_id', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter device name'}),
            'manufacturer': forms.TextInput(attrs={'placeholder': 'Enter manufacturer'}),
            'model': forms.TextInput(attrs={'placeholder': 'Enter model'}),
            'device_id': forms.TextInput(attrs={'placeholder': 'Enter device ID'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter internal notes for this device...'}),
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
        kwargs.pop('inactive_help_text', None) # Pop and discard
        cancel_url = kwargs.pop('cancel_url', None)
        ic.enable()
        ic("DeviceForm.__init__ called")
        ic(f"kwargs: {kwargs}")

        super().__init__(*args, **kwargs)
        
        # Get cancel URL from initial data or fallback
        initial = kwargs.get('initial', {})
        cancel_url = cancel_url or initial.get('cancel_url')

        if 'location' in self.fields:
            self.fields['location'].required = False
        
        # Configure crispy form helper
        self.helper = FormHelper()
        self.helper.form_class = 'model-form'
        
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_id = 'device-form'
        self.helper.form_show_errors = True
        self.helper.error_text_inline = True
        self.helper.help_text_inline = True

        # Setup Active field with proper ID and label
        checkbox_id = f"device-active-checkbox-{self.instance.pk if self.instance and self.instance.pk else 'new'}"
        self.fields['is_active'].widget.attrs.update({
            'id': checkbox_id,
            'data-device-id': str(self.instance.pk) if self.instance and self.instance.pk else 'new',
            'class': 'form-check-input active-status-checkbox',
        })
        
        # Set the label for is_active based on its current state
        if self.instance and self.instance.pk and not self.instance.is_active:
            self.fields['is_active'].label = 'Inactive'
        else:
            self.fields['is_active'].label = 'Active'
            
        self.fields['name'].label = mark_safe('<i class="bi bi-hdd-rack me-1"></i> Device Name')
        self.fields['location'].label = False
        self.fields['device_id'].label = 'Device ID'
            
        # Store original state for JavaScript
        if self.instance and self.instance.pk:
            self.fields['is_active'].widget.attrs['data-isactive-original'] = str(self.instance.is_active).lower()
            if self.instance.location:
                self.fields['is_active'].widget.attrs['data-location-original'] = str(self.instance.location.pk)
                
                # If location is inactive, device must be inactive
                if not self.instance.location.is_active:
                    self.fields['is_active'].widget.attrs['disabled'] = True
                    self.fields['is_active'].label = 'inactive'

        # CRITICAL: Always clear the help text. It is now 100% managed by JS.
        self.fields['is_active'].help_text = ''
            
        # Handle initial location if provided
        initial = kwargs.get('initial', {})
        location_initial = initial.get('location', None) or self.location
        if location_initial:
            self.location = location_initial  # Set the form's location            
            # Handle location-based activation constraints
            if not location_initial.is_active:
                ic(f"Initial location '{location_initial.name}' is inactive, disabling 'is_active' field.")
                self.fields['is_active'].widget.attrs['disabled'] = True
                self.fields['is_active'].label = 'inactive'
                    
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
                select_attrs[f'data-locationslug-{loc.pk}'] = loc.slug
            # Update the location field
            self.fields['location'].queryset = self.locations
            self.fields['location'].widget = forms.Select(
                attrs=select_attrs,
                choices=choices
            )

        self.helper.layout = Layout(
            Field('referrer', type='hidden'),
            Row(
                Column('name', css_class='col-md-8'),
                Column(
                    Div(
                        Field('is_active'),
                        css_class='is-active-container form-check form-switch pt-4'
                    ),
                    css_class='col-md-4 d-flex align-items-center'
                ),
                css_class='mb-3'
            ),
            Row(
                Column(
                    Div(
                        HTML("""
                            <label for="id_location" class="form-label d-flex justify-content-between align-items-center">
                                <span><i class="bi bi-geo-alt me-1"></i> Location</span>
                                <button type="button" hx-get="{% url 'sensors:location_create_modal' place_slug=place.slug %}"
                                        hx-target="#modal-container"
                                        data-bs-toggle="modal"
                                        data-bs-target="#modal-container"
                                        class="btn btn-sm btn-outline-primary">
                                    <i class="bi bi-plus-circle me-1"></i> Add
                                </button>
                            </label>
                        """),
                        Field('location', id='id_location'),
                    ),
                    css_class='col-md-6'
                ),
                css_class='mb-3'
            ),
            Row(
                Column('manufacturer', css_class='col-md-6'),
                Column('model', css_class='col-md-6'),
                css_class='mb-3'
            ),
            Row(
                Column('device_type', css_class='col-md-6'),
                Column('device_id', css_class='col-md-6'),
                css_class='mb-3'
            ),
            'notes',
            HTML('<hr>'),
            Div(
                HTML(f"""
                    <a href="{cancel_url}" class="btn btn-outline-secondary" data-bs-dismiss="modal">
                        <i class="bi bi-x-lg me-1"></i> Cancel
                    </a>
                """),
                HTML("""
                    <button type="submit" name="submit" class="btn btn-success">
                        <i class="bi bi-hdd-rack me-1"></i> Save
                    </button>
                """),
                css_class='d-flex justify-content-between align-items-center'
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        # ic(cleaned_data)
        if self.errors:
            # ic(self.errors.as_json())
            pass # Commented out ic(self.errors.as_json())
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
            self.add_error(None, "A device cannot be active if its location is inactive.")
            
        # Check for unique device_id within the same place
        device_id = cleaned_data.get('device_id')
        if device_id and location:
            place = location.place
            query = Device.objects.filter(
                location__place=place,
                device_id__iexact=device_id
            )
            if self.instance and self.instance.pk:
                query = query.exclude(pk=self.instance.pk)
            
            if query.exists():
                duplicate = query.first()
                self.add_error('device_id', (
                    f"A device with ID '{device_id}' already exists in this place "
                    f"(in location '{duplicate.location.name}')."
                ))
                # ic(self.errors.as_json()) # Commented out ic(self.errors.as_json())
        
        return cleaned_data

 

    def add_warning(self, field, message):
        if not hasattr(self, '_warnings'):
            self._warnings = {}
        if field not in self._warnings:
            self._warnings[field] = []
        self._warnings[field].append(message)

    def get_warnings(self):
        return getattr(self, '_warnings', {})
