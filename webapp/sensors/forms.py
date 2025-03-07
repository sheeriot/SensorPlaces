from django import forms
from .models import Sensor, InfluxSource, Place, Device, Location
from PIL import Image
from decimal import Decimal, ROUND_HALF_UP
from django.utils.text import slugify
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML, Div, Submit
from crispy_forms.bootstrap import PrependedText
from django.db import models

from icecream import ic

class SensorForm(forms.ModelForm):
    device = forms.ModelChoiceField(queryset=Device.objects.all(), widget=forms.HiddenInput())
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)
    
    class Meta:
        model = Sensor
        fields = ['device', 'name', 'sensor_type', 'unit', 'data_type', 'influx_source', 'influx_measurement', 'is_active']

    def __init__(self, *args, **kwargs):
        device = kwargs.pop('device', None)
        referrer = kwargs.pop('referrer', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0'  # Remove bottom margin as card has padding
        self.helper.form_action = ''  # Empty string means submit to same URL
        self.helper.form_id = 'sensor-form'

        if device:
            self.fields['device'].initial = device
            self.fields['device'].widget.attrs['readonly'] = True
            # Set the queryset to only include this device
            self.fields['device'].queryset = Device.objects.filter(pk=device.pk)
        
        if referrer:
            self.fields['referrer'].initial = referrer

        # Configure field properties
        self.fields['is_active'].label = "Active"
        self.fields['is_active'].help_text = None
        self.fields['data_type'].label = "Reading Source"
        self.fields['influx_source'].required = False
        self.fields['influx_source'].label = "InfluxDB Source"
        self.fields['influx_measurement'].required = False
        self.fields['influx_measurement'].label = "Measurement Name"
        self.fields['influx_measurement'].help_text = "The measurement name in InfluxDB where readings are stored"

        # Add Bootstrap classes to all fields
        for field in self.fields.values():
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs['class'] = 'form-control'

        # Determine if this is a new sensor or editing existing
        is_new = not bool(kwargs.get('instance'))
        submit_text = "Create New" if is_new else "Update"

        # Custom layout with Bootstrap grid
        self.helper.layout = Layout(
            Field('device', type='hidden'),
            Field('referrer', type='hidden'),
            Row(
                Column('name', css_class='col-md-8'),
                Column(
                    Div(
                        Field('is_active', wrapper_class='form-check form-switch'),
                        css_class='d-flex align-items-center h-100'
                    ),
                    css_class='col-md-4'
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
                style='display: none;'
            ),
            Div(
                HTML('<hr class="mt-4">'),
                Div(
                    HTML("""
                        <a href="{% url 'sensors:device_detail' place_slug=device.location.place.slug pk=device.pk %}" 
                           class="btn btn-outline-secondary">
                            <i class="bi bi-x-lg me-1"></i>Cancel
                        </a>
                    """),
                    HTML(f"""
                        <button type="submit" class="btn btn-primary">
                            <i class="bi bi-thermometer me-1"></i>{submit_text}
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

        if not device:
            raise forms.ValidationError("Device is required")

        if data_type == 'INFLUX':
            if not influx_source:
                self.add_error('influx_source', "InfluxDB source is required when data type is InfluxDB")
            if not influx_measurement:
                self.add_error('influx_measurement', "InfluxDB measurement is required when data type is InfluxDB")

        return cleaned_data

class PlaceForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)
    slug = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Place
        fields = ['name', 'is_active', 'latitude', 'longitude', 'slug']

    def __init__(self, *args, **kwargs):
        referrer = kwargs.pop('referrer', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0'  # Remove bottom margin as card has padding
        
        # Add referrer to form if provided
        if referrer:
            self.fields['referrer'].initial = referrer

        # Configure field properties
        self.fields['is_active'].label = "Active"
        self.fields['is_active'].help_text = None
        
        # If this is an existing Place, preserve its slug
        if self.instance and self.instance.pk:
            self.fields['slug'].initial = self.instance.slug
        
        # Add Bootstrap classes and configure fields
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.HiddenInput, forms.CheckboxInput)):
                field.widget.attrs['class'] = 'form-control'

        # Determine if this is a new place or editing existing
        is_new = not bool(kwargs.get('instance'))
        submit_text = "Create Place" if is_new else "Update Place"

        # Custom layout with Bootstrap grid
        self.helper.layout = Layout(
            Field('slug', type='hidden'),
            Field('referrer', type='hidden'),
            Row(
                Column('name', css_class='col-md-8'),
                Column(
                    Div(
                        Field('is_active', wrapper_class='form-check form-switch'),
                        css_class='d-flex align-items-center h-100'
                    ),
                    css_class='col-md-4'
                ),
                css_class='mb-3'
            ),
            Row(
                Column('latitude', css_class='col-md-6'),
                Column('longitude', css_class='col-md-6'),
                css_class='mb-3'
            ),
            Div(
                HTML('<div id="preview-map" class="preview-map mb-3"></div>'),
                css_class='mb-3'
            ),
            Div(
                HTML('<hr class="mt-4">'),
                Div(
                    HTML("""
                        <a href="{% url 'sensors:place_list' %}" 
                           class="btn btn-outline-secondary">
                            <i class="bi bi-x-lg me-1"></i>Cancel
                        </a>
                    """),
                    HTML(f"""
                        <button type="submit" class="btn btn-primary">
                            <i class="bi bi-house-gear me-1"></i>{submit_text}
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

    def clean_site_plan(self):
        site_plan = self.cleaned_data.get('site_plan')
        if site_plan:
            # Check image dimensions
            img = Image.open(site_plan)
            min_width, min_height = 1024, 768
            
            if img.width < min_width or img.height < min_height:
                raise forms.ValidationError(
                    f'Image dimensions must be at least {min_width}x{min_height} pixels. '
                    f'Uploaded image is {img.width}x{img.height} pixels.'
                )
        return site_plan

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

class ReadOnlyLocationWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        widgets = [
            forms.Select(attrs={'class': 'form-control', 'readonly': True, 'disabled': True}),
            forms.HiddenInput()
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return [value, value]  # Same value for both select and hidden
        return [None, None]

class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['name', 'location', 'device_type', 'manufacturer', 'model', 'serial_number', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter device name'}),
            'serial_number': forms.TextInput(attrs={'placeholder': 'Enter serial number'}),
            'manufacturer': forms.TextInput(attrs={'placeholder': 'Enter manufacturer'}),
            'model': forms.TextInput(attrs={'placeholder': 'Enter model'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get place and location from initial data
        initial = kwargs.get('initial', {})
        place = initial.get('place')
        initial_location = initial.get('location')

        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0'

        # Configure location field based on context
        if initial_location:
            self.fields['location'].queryset = Location.objects.filter(pk=initial_location.pk)
            self.fields['location'].initial = initial_location
            self.fields['location'].widget = forms.HiddenInput()
        elif place:
            self.fields['location'].queryset = Location.objects.filter(
                place=place,
                is_active=True
            ).order_by('name')
            self.fields['location'].widget.attrs['class'] = 'form-select'

        # Configure field labels and help text
        self.fields['is_active'].label = "Active"
        self.fields['is_active'].help_text = None
        self.fields['device_type'].label = "Device Type"
        
        # Custom layout with Bootstrap grid
        self.helper.layout = Layout(
            # Hidden location field if provided
            'location' if initial_location else None,
            
            # Name and Device Type row
            Row(
                Column('name', css_class='col-md-6'),
                Column('device_type', css_class='col-md-6'),
                css_class='mb-3'
            ),
            
            # Manufacturer and Model row
            Row(
                Column('manufacturer', css_class='col-md-6'),
                Column('model', css_class='col-md-6'),
                css_class='mb-3'
            ),
            
            # Serial Number row
            Row(
                Column('serial_number', css_class='col-12'),
                css_class='mb-3'
            ),
            
            # Footer with Active switch and buttons
            Div(
                HTML('<hr>'),
                Div(
                    # Left side - Active switch
                    Div(
                        Field(
                            'is_active',
                            wrapper_class='form-check form-switch',
                            css_class='form-check-input'
                        ),
                        css_class='d-flex align-items-center'
                    ),
                    # Right side - Buttons
                    Div(
                        HTML("""
                            <a href="{% if location %}
                                      {% url 'sensors:location_detail' place_slug=place.slug pk=location.pk %}
                                    {% else %}
                                      {% url 'sensors:place_detail' place_slug=place.slug %}
                                    {% endif %}"
                               class="btn btn-outline-secondary me-2">
                                <i class="bi bi-x-lg me-1"></i>Cancel
                            </a>
                        """),
                        Submit(
                            'submit',
                            'Create Device',
                            css_class='btn btn-primary',
                            prepend='<i class="bi bi-hdd-rack me-1"></i>'
                        ),
                        css_class='d-flex gap-2'
                    ),
                    css_class='d-flex justify-content-between align-items-center'
                ),
                css_class='mt-4'
            )
        )

        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.HiddenInput, forms.CheckboxInput)):
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        # Ensure the location value from the hidden input is used
        if 'location' in cleaned_data and isinstance(cleaned_data['location'], list):
            cleaned_data['location'] = cleaned_data['location'][1]  # Use the hidden input value
        return cleaned_data

    def clean_serial_number(self):
        serial_number = self.cleaned_data.get('serial_number')
        manufacturer = self.cleaned_data.get('manufacturer')
        model = self.cleaned_data.get('model')

        if serial_number:
            # Get existing devices with the same serial number, excluding current device if editing
            existing_devices = Device.objects.filter(serial_number=serial_number)
            if self.instance.pk:
                existing_devices = existing_devices.exclude(pk=self.instance.pk)

            if existing_devices.exists():
                # Check if any device with same serial number has matching manufacturer or model
                matching_devices = existing_devices.filter(
                    models.Q(manufacturer=manufacturer) | models.Q(model=model)
                )

                if matching_devices.exists():
                    # If manufacturer or model matches, raise validation error
                    raise forms.ValidationError(
                        "A device with this serial number already exists with the same manufacturer or model."
                    )
                else:
                    # If no manufacturer/model match, just add a warning
                    self.add_warning(
                        'serial_number',
                        'This serial number is already in use by another device.'
                    )

        return serial_number

    def add_warning(self, field, message):
        """Add a warning message to a field without preventing form submission"""
        if not hasattr(self, '_warnings'):
            self._warnings = {}
        if field not in self._warnings:
            self._warnings[field] = []
        self._warnings[field].append(message)

    def get_warnings(self):
        """Return all warning messages"""
        return getattr(self, '_warnings', {})

class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0'
        
        # Configure field properties
        self.fields['is_active'].label = "Active"
        self.fields['is_active'].help_text = None
        
        # Determine if this is a new location or editing existing
        is_new = not bool(kwargs.get('instance'))
        submit_text = "Create Location" if is_new else "Update Location"
        
        # Custom layout with Bootstrap grid
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-8'),
                Column(
                    Div(
                        Field(
                            'is_active', 
                            wrapper_class='form-check form-switch form-switch-lg'
                        ),
                        css_class='d-flex align-items-center h-100'
                    ),
                    css_class='col-md-4'
                ),
                css_class='mb-3'
            ),
            Div(
                HTML('<hr class="mt-4">'),
                Div(
                    HTML("""
                        <a href="{% url 'sensors:place_locations' place_slug=place.slug %}" 
                           class="btn btn-outline-secondary">
                            <i class="bi bi-x-lg me-1"></i>Cancel
                        </a>
                    """),
                    Submit(
                        'submit',
                        submit_text,
                        css_class='btn btn-primary',
                        prepend='<i class="bi bi-save me-1"></i>'
                    ),
                    css_class='d-flex justify-content-between align-items-center'
                ),
                css_class='mt-3'
            )
        ) 