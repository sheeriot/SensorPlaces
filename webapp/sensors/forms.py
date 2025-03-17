from django import forms
from .models import Sensor, Place, Device, Location  # InfluxSource,
from PIL import Image
from decimal import Decimal, ROUND_HALF_UP
from django.utils.text import slugify
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML, Div, Submit  # TemplateNameMixin
# from crispy_forms.bootstrap import PrependedText, FormActions
from django.db import models

from django.db.models import Count, Q
from django.template.loader import render_to_string

from icecream import ic
from django.urls import reverse


class PlaceForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)
    slug = forms.CharField(widget=forms.HiddenInput(), required=False)
    siteplan_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'data-bs-toggle': 'tooltip',
            'title': 'Upload a siteplan image (minimum 200x200)',
        }),
        help_text='Upload a siteplan image (minimum 200x200 pixels)'
    )

    class Meta:
        model = Place
        fields = ['name', 'is_active', 'latitude', 'longitude', 'slug', 'siteplan_image']
        widgets = {
            'is_active': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input active-checkbox',
                    'data-active-label': 'Active',
                    'data-inactive-label': 'inactive'
                }
            ),
            'latitude': forms.NumberInput(attrs={
                'step': '0.00001',
                'class': 'form-control form-control-sm',
                'style': 'width: 110px;',
                'min': -90,
                'max': 90,
                'pattern': r'-?\d+\.\d{0,5}',
                'maxlength': 10
            }),
            'longitude': forms.NumberInput(attrs={
                'step': '0.00001',
                'class': 'form-control form-control-sm',
                'style': 'width: 110px;',
                'min': -180,
                'max': 180,
                'pattern': r'-?\d+\.\d{0,5}',
                'maxlength': 11
            })
        }

    def __init__(self, *args, **kwargs):
        inactive_help_text = kwargs.pop('inactive_help_text', None)
        # Remove the referrer pop - we'll handle it through initial data instead
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0 model-form'
        self.helper.form_id = f"place-form-{self.instance.pk if self.instance and self.instance.pk else 'new'}"
        self.helper.form_show_errors = True
        self.helper.error_text_inline = True
        self.helper.help_text_inline = True
        
        # If this is an existing Place, preserve its slug
        if self.instance and self.instance.pk:
            self.fields['slug'].initial = self.instance.slug
        
        # Configure field properties
        # Setup Active field with proper ID and label
        checkbox_id = f"place-active-checkbox-{self.instance.pk if self.instance and self.instance.pk else 'new'}"
        self.fields['is_active'].widget.attrs.update({
            'id': checkbox_id,
            'data-place-id': str(self.instance.pk) if self.instance and self.instance.pk else 'new'
        })
        
        # Set the label based on the current state
        if self.instance and self.instance.pk and not self.instance.is_active:
            self.fields['is_active'].label = 'inactive'
        else:
            self.fields['is_active'].label = 'Active'
        
        # Set help text for inactive state if provided
        if inactive_help_text:
            self.fields['is_active'].help_text = inactive_help_text
        
        self.fields['latitude'].label = None
        self.fields['longitude'].label = None

        # Add Bootstrap classes
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.HiddenInput, forms.CheckboxInput)):
                field.widget.attrs['class'] = 'form-control'

        # Determine if new or existing
        is_new = not bool(kwargs.get('instance'))

        # Add site plan preview if it exists
        siteplan_layout = []
        if self.instance and self.instance.siteplan_image:
            siteplan_layout = [
                Div(
                    HTML("""
                        <div class="card mb-3">
                            <div class="card-body text-center">
                                <img src="{{ object.siteplan_image.url }}" 
                                     alt="Site Plan" 
                                     class="img-fluid mb-2" 
                                     style="max-height: 300px;">
                            </div>
                        </div>
                    """)
                )
            ]

        # Update the site plan field in the form
        self.fields['siteplan_image'].widget.attrs.update({
            'class': 'form-control',
            'accept': 'image/*'
        })
        if self.instance and self.instance.siteplan_image:
            self.fields['siteplan_image'].help_text = f'Upload a new site plan image to replace the current one (minimum 200x200 pixels)'
        else:
            self.fields['siteplan_image'].help_text = 'Upload a site plan image (minimum 200x200 pixels)'

        self.helper.layout = Layout(
            Field('slug', type='hidden'),
            Field('referrer', type='hidden'),
            Div(
                Div(
                    Div('name', css_class='col-md-6'),
                    Div(
                        Field(
                            'is_active',
                            template='sensors/partials/active_status_checkbox.html',
                            model_name='place',  # or 'location' for LocationForm
                            instance_pk=self.instance.pk if self.instance and self.instance.pk else 'new',
                        ),
                        css_class='col-md-6 d-flex align-items-center'
                    ),
                    css_class='row mb-3'
                ),
                css_class='form-group'
            ),
            # Fieldset for coordinates and map
            Div(
                HTML("""
                    <fieldset class="border rounded-2 p-3">
                        <legend class="float-none w-auto px-2 mb-0 fs-5 bg-secondary-subtle">
                            <i class="bi bi-geo-alt me-1"></i>Place Coordinates
                        </legend>
                        <div class="d-flex justify-content-center gap-3 mb-2">
                            <div class="input-group input-group-sm flex-nowrap" style="width: 220px;">
                                <span class="input-group-text" style="width: 45px;">Lat</span>
                                {{ form.latitude }}
                            </div>
                            <div class="input-group input-group-sm flex-nowrap" style="width: 220px;">
                                <span class="input-group-text" style="width: 45px;">Lng</span>
                                {{ form.longitude }}
                            </div>
                        </div>
                        <div id="place-form-map" class="rounded border" style="height: 400px;"></div>
                    </fieldset>
                """),
                css_class='mb-3'
            ),
            Row(
                Column('siteplan_image', css_class='col-12'),
                css_class='mb-3'
            ),
            *siteplan_layout,
            Div(
                HTML('<hr class="mt-4">'),
                Div(
                    HTML("""
                        <a href="{% url 'sensors:place_list' %}" 
                           class="btn btn-outline-secondary">
                            <i class="bi bi-x-lg me-1"></i>Cancel
                        </a>
                    """),
                    HTML("""
                        <button type="submit" class="btn btn-success">
                            <i class="bi bi-house-gear me-1"></i>{% if not object %}Create{% else %}Save{% endif %}
                        </button>
                    """),
                    css_class='d-flex justify-content-between align-items-center'
                ),
                css_class='mt-3'
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        current_slug = cleaned_data.get('slug')
        
        if name:
            # Only generate new slug if this is a new place or slug is missing
            if not current_slug:
                base_slug = slugify(name)
                slug = base_slug
                # Ensure unique slug
                counter = 1
                # Don't check against self when verifying uniqueness
                slug_qs = Place.objects.filter(slug=slug)
                if self.instance and self.instance.pk:
                    slug_qs = slug_qs.exclude(pk=self.instance.pk)
                
                while slug_qs.exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                    slug_qs = Place.objects.filter(slug=slug)
                    if self.instance and self.instance.pk:
                        slug_qs = slug_qs.exclude(pk=self.instance.pk)
                
                cleaned_data['slug'] = slug
            else:
                # Keep existing slug
                cleaned_data['slug'] = current_slug
        
        return cleaned_data

    def clean_siteplan_image(self):
        siteplan_image = self.cleaned_data.get('siteplan_image')
        
        if siteplan_image:
            try:
                # Always reset to beginning
                siteplan_image.seek(0)
                
                img = Image.open(siteplan_image)
                
                # Basic dimension check
                if img.width < 200 or img.height < 200:
                    raise forms.ValidationError(
                        f'Image must be at least 200x200 pixels. '
                        f'Uploaded image is {img.width}x{img.height} pixels.'
                    )
                
                # Reset file pointer one final time
                siteplan_image.seek(0)
                return siteplan_image
                    
            except Exception as e:
                raise forms.ValidationError(f"Image validation failed: {str(e)}")
        
        return siteplan_image

    def clean_latitude(self):
        lat = self.cleaned_data['latitude']
        if lat is not None:
            # Round to 5 decimal places
            lat = Decimal(str(lat)).quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP)
            # Validate range
            if lat < -90 or lat > 90:
                raise forms.ValidationError("Latitude must be between -90 and 90 degrees")
        return lat

    def clean_longitude(self):
        lon = self.cleaned_data['longitude']
        if lon is not None:
            # Round to 5 decimal places
            lon = Decimal(str(lon)).quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP)
            # Validate range
            if lon < -180 or lon > 180:
                raise forms.ValidationError("Longitude must be between -180 and 180 degrees")
        return lon

class PlaceDeleteForm(forms.Form):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    confirm_name = forms.CharField(
        label='Confirm deletion',
        help_text='Type the name of the place to confirm deletion',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Type the place name to confirm'
        })
    )

    def __init__(self, *args, place=None, inactive_help_text=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.place = place
        self.inactive_help_text = inactive_help_text
        
        # Setup crispy form
        self.helper = FormHelper()
        self.helper.form_id = 'place-delete-form'
        self.helper.form_class = 'model-form'
        self.helper.form_method = 'post'
        
        # Update help text if place has active locations
        if place:
            active_locations = place.locations.filter(is_active=True)
            active_location_count = active_locations.count()
            
            if active_location_count > 0:
                # Get active devices count
                active_devices_count = 0
                active_locations_list = []
                
                for location in active_locations:
                    location_active_devices = location.devices.filter(is_active=True).count()
                    active_devices_count += location_active_devices
                    active_locations_list.append(
                        f'<li><i class="bi bi-geo-alt text-muted me-1"></i>{location.name} '
                        f'<small class="text-muted">({location_active_devices} active devices)</small></li>'
                    )
                
                warning_text = mark_safe(
                    '<div class="alert alert-warning">'
                    f'<i class="bi bi-exclamation-triangle me-2"></i>'
                    f'<strong>Warning:</strong> This place has {active_location_count} active '
                    f'location{"s" if active_location_count > 1 else ""} with {active_devices_count} '
                    f'active device{"s" if active_devices_count > 1 else ""}.'
                    f'<ul class="list-unstyled mb-0 mt-2 ms-3">{"".join(active_locations_list)}</ul>'
                    '</div>'
                )
                
                self.fields['confirm_name'].help_text = mark_safe(
                    f'{warning_text}<p class="text-danger mt-2">Type <strong>{place.name}</strong> to confirm deletion</p>'
                )
            else:
                self.fields['confirm_name'].help_text = mark_safe(
                    f'Type <strong>{place.name}</strong> to confirm deletion'
                )
            
            # Add the inactive help text if provided
            if self.inactive_help_text:
                self.fields['confirm_name'].help_text = mark_safe(
                    f'{self.fields["confirm_name"].help_text}<div class="mt-2">{self.inactive_help_text}</div>'
                )
        
        # Set up the form layout
        self.helper.layout = Layout(
            Field('referrer', type='hidden'),
            Div(
                HTML("""
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        <strong>Warning:</strong> This action cannot be undone!
                    </div>
                """),
                css_class='mb-3'
            ),
            'confirm_name',
            Div(
                HTML('<hr class="mt-4">'),
                Div(
                    HTML("""
                        <a href="{% if referrer %}{{ referrer }}{% else %}{% url 'sensors:place_detail' place_slug=place.slug %}{% endif %}" 
                           class="btn btn-outline-secondary">
                            <i class="bi bi-x-lg me-1"></i>Cancel
                        </a>
                    """),
                    HTML("""
                        <button type="submit" class="btn btn-danger">
                            <i class="bi bi-trash me-1"></i>Delete Place
                        </button>
                    """),
                    css_class='d-flex justify-content-between align-items-center'
                ),
                css_class='mt-3'
            )
        )

    def clean_confirm_name(self):
        confirm_name = self.cleaned_data.get('confirm_name')
        if self.place and confirm_name != self.place.name:
            raise forms.ValidationError(f"The name you entered doesn't match the place name. Please type '{self.place.name}' to confirm.")
        return confirm_name

class LocationForm(forms.ModelForm):
    # Form-specific fields (not in model) - no need to include these in Meta.fields
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)
    confirm_deactivate = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={  
            'class': 'form-control',
            'placeholder': 'Type the number of active devices:'
        })
    )

    class Meta:
        model = Location
        # Only include model fields here
        fields = ['name', 'place', 'is_active']
        widgets = {
            'place': forms.HiddenInput(),
            'is_active': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input active-checkbox',
                    'data-active-label': 'Active',
                    'data-inactive-label': 'inactive'
            })
        }

    def __init__(self, *args, **kwargs):
        # Pop special parameters before calling parent __init__
        self.place = kwargs.pop('place', None)
        self.locations = kwargs.pop('locations', None)
        self.devices_active = kwargs.pop('devices_active', None)
        inactive_help_text = kwargs.pop('inactive_help_text', None)
        
        super().__init__(*args, **kwargs)

        # Set initial data for place if this is a new location
        if self.place and not self.instance.pk:
            self.initial['place'] = self.place.pk  # Use the primary key
            # Also set it on the instance to ensure it's available during validation
            self.instance.place = self.place
        
        # Setup form ID and classes
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0 model-form'
        self.helper.form_id = f"location-form-{self.instance.pk if self.instance and self.instance.pk else 'new'}"
        self.helper.form_show_errors = True
        self.helper.error_text_inline = True
        self.helper.help_text_inline = True
        
        # Default label and help text
        self.fields['is_active'].label = 'Active'
        self.fields['is_active'].help_text = ''
        
        # Configure field properties
        # Setup Active field with proper ID and label
        checkbox_id = f"location-active-checkbox-{self.instance.pk if self.instance and self.instance.pk else 'new'}"
        self.fields['is_active'].widget.attrs.update({
            'id': checkbox_id,
            'data-location-id': str(self.instance.pk) if self.instance and self.instance.pk else 'new'
        })
        
        # For both new and existing locations, if place is inactive, force location to be inactive
        if self.place and not self.place.is_active:
            # Quick check on existing location
            if self.instance and self.instance.pk and self.instance.is_active:
                # If existing location was active but place is inactive, update the instance
                self.instance.is_active = False
                self.instance.save()
            
            # Force location to be inactive if place is inactive
            self.fields['is_active'].initial = False  # This is important!
            self.fields['is_active'].widget.attrs['disabled'] = True
            self.fields['is_active'].label = 'inactive'
            
            help_text_inactive = mark_safe(
                '<div class="form-text text-muted mt-2">'
                f'<i class="bi bi-house-gear me-2"></i>'
                f'Cannot activate: Place {self.place.name} is inactive'
                '</div>'
            )
            self.fields['is_active'].help_text = help_text_inactive
        
        # Handle existing location with active devices
        elif self.instance and self.instance.pk:
            # Set the label based on the current state
            if not self.instance.is_active:
                self.fields['is_active'].label = 'inactive'
            
            # We don't need to generate our own help_text here
            # Just use what comes from the view via inactive_help_text
        
        # For new locations at active places, set default help text if needed
        else:
            self.fields['is_active'].initial = True
        
        # Set help text for inactive state if provided from view
        if inactive_help_text:
            self.fields['is_active'].help_text = inactive_help_text

        # First, define a cancel_url variable
        cancel_url = "{% url 'sensors:location_detail' place_slug=place.slug pk=object.pk %}"
        if not self.instance.pk:
            cancel_url = "{% url 'sensors:place_detail' place_slug=place.slug %}"

        # Then update the layout
        self.helper.layout = Layout(
            Div(
                Div(
                    Div('name', css_class='col-md-6'),
                    Div(
                        Field(
                            'is_active',
                            template='sensors/partials/active_status_checkbox.html',
                            model_name='location',
                            instance_pk=self.instance.pk if self.instance and self.instance.pk else 'new',
                        ),
                        css_class='col-md-6 d-flex align-items-center'
                    ),
                    css_class='row mb-3'
                ),
                css_class='form-group'
            ),
            # Static display of Place name
            Div(
                Div(
                    HTML(f"""
                        <div class="form-group">
                            <label class="form-label">Place</label>
                            <div class="form-control-static">
                                <i class="bi bi-house-gear me-1"></i>
                                {self.place.name if self.place else 'Unknown'}
                            </div>
                        </div>
                    """),
                    css_class='col-12'
                ),
                css_class='row mb-3'
            ),
            Div(
                Field('referrer', type='hidden'),
                Field('place', type='hidden'),  # Make sure place is included
                css_class='mb-3'
            ),
            Div(
                Field('confirm_deactivate'),
                css_class='mb-3 d-none',
                css_id='confirm-deactivate-container'
            ),
            Div(
                HTML('<hr class="mt-4">'),
                Div(
                    HTML(f"""
                        <a href="{cancel_url}" 
                        class="btn btn-outline-secondary">
                            <i class="bi bi-x-lg me-1"></i>Cancel
                        </a>
                    """),
                    HTML("""
                        <button type="submit" class="btn btn-success">
                            <i class="bi bi-geo-alt me-1"></i>{% if not object %}Create{% else %}Save{% endif %}
                        </button>
                    """),
                    css_class='d-flex justify-content-between align-items-center'
                ),
                css_class='mt-3'
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure place is in cleaned_data
        if self.place and 'place' not in cleaned_data:
            cleaned_data['place'] = self.place
            # Also set it on the instance
            self.instance.place = self.place
        
        # Get is_active value, defaulting to False if not present
        is_active = cleaned_data.get('is_active', False)
        confirm_deactivate = cleaned_data.get('confirm_deactivate')

        # Ensure location is inactive if place is inactive
        if is_active and self.place and not self.place.is_active:
            cleaned_data['is_active'] = False
            self.add_error('is_active', "Location cannot be active when its place is inactive.")
        
        # Handle deactivation confirmation - check if we're changing from active to inactive
        if self.instance and self.instance.pk and self.instance.is_active and not is_active:
            # Count active devices
            active_device_count = self.instance.devices.filter(is_active=True).count()
            
            # Only require confirmation if there are active devices
            if active_device_count > 0:
                if not confirm_deactivate:
                    raise forms.ValidationError({
                        'confirm_deactivate': f"Please type {active_device_count} to confirm deactivation of {active_device_count} active device(s)."
                    })
                
                try:
                    if int(confirm_deactivate) != active_device_count:
                        raise forms.ValidationError({
                            'confirm_deactivate': f"Incorrect confirmation number. Please type {active_device_count} to confirm."
                        })
                except ValueError:
                    raise forms.ValidationError({
                        'confirm_deactivate': "Please enter a valid number."
                    })
        
        return cleaned_data

    def is_valid(self):
        # Ensure place is set on the instance before validation
        if self.place and not self.instance.place_id:
            self.instance.place = self.place
        
        return super().is_valid()

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
                'class': 'me-2 checkboxinput active-checkbox',
                'data-active-label': 'Active',
                'data-inactive-label': 'inactive'
            })
        }

    def __init__(self, *args, **kwargs):
        self.place = kwargs.pop('place', None)
        self.locations = kwargs.pop('locations', None)
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
        
        # Store original state for JavaScript
        if self.instance and self.instance.pk:
            self.fields['is_active'].widget.attrs['data-isactive-original'] = str(self.instance.is_active).lower()
            if self.instance.location:
                self.fields['is_active'].widget.attrs['data-location-original'] = str(self.instance.location.pk)
        
        # Set the label based on the current state
        if self.instance and self.instance.pk and not self.instance.is_active:
            self.fields['is_active'].label = 'inactive'
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

        initial = kwargs.get('initial', {})
        location_initial = initial.get('location', None)
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
                Column('name', css_class='col-6'),
                Column('device_type', css_class='col-4'),
                css_class='mb-2'
            ),
            Row(
                Column(
                    Field(
                        'is_active',
                        template='sensors/partials/active_status_checkbox.html',
                        css_id='div_id_is_active'
                    ),
                    css_class='col-12'
                ),
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
        location = cleaned_data.get('location')
        
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
        
        # Ensure device is inactive if location is inactive
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

class SensorForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Sensor
        fields = ['device', 'name', 'is_active', 'sensor_type', 'unit', 'data_type', 'influx_source', 'influx_measurement']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter sensor name'}),
            'device': forms.HiddenInput(),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input active-checkbox',
                'data-active-label': 'Active',
                'data-inactive-label': 'inactive'
            })
        }

    def __init__(self, *args, **kwargs):
        self.place = kwargs.pop('place', None)
        self.device = kwargs.pop('device', None)
        inactive_help_text = kwargs.pop('inactive_help_text', None)
        super().__init__(*args, **kwargs)
        
        # Configure crispy form helper
        self.helper = FormHelper()
        self.helper.form_id = 'sensor-form'
        self.helper.form_class = 'model-form'

        # Setup Active field with proper ID and label
        checkbox_id = f"sensor-active-checkbox-{self.instance.pk if self.instance and self.instance.pk else 'new'}"
        self.fields['is_active'].widget.attrs.update({
            'id': checkbox_id,
            'data-sensor-id': str(self.instance.pk) if self.instance and self.instance.pk else 'new'
        })
        
        # Set the label based on the current state
        if self.instance and self.instance.pk and not self.instance.is_active:
            self.fields['is_active'].label = 'inactive'
        else:
            self.fields['is_active'].label = 'Active'
        
        # Set help text for inactive state if provided from view
        if inactive_help_text:
            self.fields['is_active'].help_text = inactive_help_text

        # If we have a device (either from kwargs or from instance), use it
        if not self.device and self.instance and self.instance.pk and self.instance.device:
            self.device = self.instance.device

        # If we have a device, handle device-based activation constraints
        if self.device:
            # Set the device field to the provided device
            self.initial['device'] = self.device
            self.fields['device'].initial = self.device
            
            # If device is inactive, sensor must be inactive
            if not self.device.is_active:
                self.fields['is_active'].initial = False
                self.fields['is_active'].widget.attrs['disabled'] = True
                self.fields['is_active'].label = 'inactive'
                
                # Only set help text if not already provided from view
                if not inactive_help_text:
                    self.fields['is_active'].help_text = mark_safe(
                        '<div class="form-text text-warning-emphasis mt-2">'
                        f'<i class="bi bi-hdd-rack me-2"></i>'
                        f'Sensor cannot be active because Device "{self.device.name}" is inactive.'
                        '</div>'
                    )

        # Layout with crispy forms
        self.helper.layout = Layout(
            Field('device', type='hidden'),
            Field('referrer', type='hidden'),
            # Static display of Device name
            Div(
                Div(
                    HTML(f"""
                        <div class="form-group">
                            <label class="form-label">Device</label>
                            <div class="form-control-static">
                                <i class="bi bi-hdd-rack me-1"></i>
                                {self.device.name if self.device else 'Unknown'}
                            </div>
                        </div>
                    """),
                    css_class='col-12'
                ),
                css_class='row mb-3'
            ),
            Row(
                Column('name', css_class='col-md-12'),
                css_class='mb-3'
            ),
            Row(
                Field(
                    'is_active',
                    template='sensors/partials/active_status_checkbox.html',
                    model_name='sensor',
                    instance_pk=self.instance.pk if self.instance and self.instance.pk else 'new',
                ),
                css_class='mb-3'
            ),
            Row(
                Column('sensor_type', css_class='col-md-6'),
                Column('unit', css_class='col-md-6'),
                css_class='mb-3'
            ),
            Row(
                Column('data_type', css_class='col-md-12'),
                css_class='mb-3'
            ),
            Div(
                Row(
                    Column('influx_source', css_class='col-md-12'),
                    css_class='mb-3'
                ),
                Row(
                    Column('influx_measurement', css_class='col-md-12'),
                    css_class='mb-3'
                ),
                css_class='influx-fields',
                id='influx-fields'
            ),
            Div(
                HTML('<hr class="mt-4">'),
                Div(
                    HTML("""
                        <a href="{{ form.referrer.value|default:cancel_fallback_url }}" 
                           class="btn btn-outline-secondary">
                            <i class="bi bi-x-lg me-1"></i>Cancel
                        </a>
                    """),
                    HTML("""
                        <button type="submit" class="btn btn-success">
                            <i class="bi bi-thermometer me-1"></i>{% if not object %}Create{% else %}Save{% endif %}
                        </button>
                    """),
                    css_class='d-flex justify-content-between align-items-center'
                ),
                css_class='mt-3'
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        data_type = cleaned_data.get('data_type')
        influx_source = cleaned_data.get('influx_source')
        influx_measurement = cleaned_data.get('influx_measurement')
        device = cleaned_data.get('device')

        # Ensure device is set
        if not device and self.device:
            cleaned_data['device'] = self.device
            self.instance.device = self.device

        # Validate device is provided
        if not device:
            raise forms.ValidationError("Device is required")

        # Ensure sensor is inactive if device is inactive
        if device and not device.is_active and cleaned_data.get('is_active', False):
            cleaned_data['is_active'] = False
            self.add_error('is_active', "Sensor cannot be active when its device is inactive.")

        # Validate InfluxDB fields if data type is INFLUX
        if data_type == 'INFLUX':
            if not influx_source:
                self.add_error('influx_source', "InfluxDB source is required when data type is InfluxDB")
            if not influx_measurement:
                self.add_error('influx_measurement', "InfluxDB measurement is required when data type is InfluxDB")

        return cleaned_data

    def is_valid(self):
        # Ensure device is set on the instance before validation
        if hasattr(self, 'device') and self.device and not self.instance.device_id:
            self.instance.device = self.device
        return super().is_valid()
