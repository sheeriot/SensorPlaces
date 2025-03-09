from django import forms
from .models import Sensor, InfluxSource, Place, Device, Location
from PIL import Image
from decimal import Decimal, ROUND_HALF_UP
from django.utils.text import slugify
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML, Div, Submit
from crispy_forms.bootstrap import PrependedText, FormActions
from django.db import models

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
        self.helper.form_show_errors = True
        self.helper.error_text_inline = False
        self.helper.help_text_inline = False

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
                    Submit(
                        'submit',
                        mark_safe('<i class="bi bi-thermometer me-1"></i>' + ('Create' if is_new else 'Save')),
                        css_class='btn btn-success'
                    ),
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
    site_plan = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'data-bs-toggle': 'tooltip',
            'title': 'Upload a site plan image (minimum 200x200)',
        }),
        help_text='Upload a site plan image (minimum 200x200 pixels)'
    )

    class Meta:
        model = Place
        fields = ['name', 'is_active', 'latitude', 'longitude', 'slug', 'site_plan']
        widgets = {
            'latitude': forms.NumberInput(attrs={
                'step': '0.00001',
                'class': 'form-control',
                'style': 'width: 140px;',
                'min': -90,
                'max': 90,
                'pattern': r'-?\d+\.\d{0,5}'
            }),
            'longitude': forms.NumberInput(attrs={
                'step': '0.00001',
                'class': 'form-control',
                'style': 'width: 140px;',
                'min': -180,
                'max': 180,
                'pattern': r'-?\d+\.\d{0,5}'
            })
        }

    def __init__(self, *args, **kwargs):
        referrer = kwargs.pop('referrer', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0'
        self.helper.form_show_errors = True
        self.helper.error_text_inline = True
        self.helper.help_text_inline = True
        
        if referrer:
            self.fields['referrer'].initial = referrer

        # If this is an existing Place, preserve its slug
        if self.instance and self.instance.pk:
            self.fields['slug'].initial = self.instance.slug
        
        # Configure field properties
        self.fields['is_active'].label = ""  # Remove label since we use custom template
        self.fields['is_active'].help_text = None
        
        self.fields['latitude'].label = None
        self.fields['longitude'].label = None

        # Add Bootstrap classes
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.HiddenInput, forms.CheckboxInput)):
                field.widget.attrs['class'] = 'form-control'

        # Determine if new or existing
        is_new = not bool(kwargs.get('instance'))

        # Add site plan preview if it exists
        site_plan_layout = []
        if self.instance and self.instance.site_plan:
            site_plan_layout = [
                Div(
                    HTML("""
                        <div class="card mb-3">
                            <div class="card-body text-center">
                                <img src="{{ object.site_plan.url }}" 
                                     alt="Site Plan" 
                                     class="img-fluid mb-2" 
                                     style="max-height: 300px;">
                            </div>
                        </div>
                    """)
                )
            ]

        # Update the site plan field in the form
        self.fields['site_plan'].widget.attrs.update({
            'class': 'form-control',
            'accept': 'image/*'
        })
        if self.instance and self.instance.site_plan:
            self.fields['site_plan'].help_text = f'Upload a new site plan image to replace the current one (minimum 200x200 pixels)'
        else:
            self.fields['site_plan'].help_text = 'Upload a site plan image (minimum 200x200 pixels)'

        self.helper.layout = Layout(
            Field('slug', type='hidden'),
            Field('referrer', type='hidden'),
            Row(
                Column('name', css_class='col-md-8'),
                Column(
                    Div(
                        Field(
                            'is_active',
                            template='sensors/includes/custom_switch.html',
                            wrapper_class='form-check form-switch d-flex align-items-center'
                        ),
                        css_class='h-100 d-flex align-items-center justify-content-start'
                    ),
                    css_class='col-md-4'
                ),
                css_class='mb-3'
            ),
            Row(
                Div(
                    HTML("""
                        <div class="text-center mb-2">
                            <i class="bi bi-globe2 mx-1"></i>
                            <i class="bi bi-compass mx-1"></i>
                            <i class="bi bi-geo-alt mx-1"></i>
                            <i class="bi bi-map mx-1"></i>
                            <i class="bi bi-pin-map mx-1"></i>
                        </div>
                    """),
                    Div(
                        HTML("""
                            <div class="input-group" style="width: fit-content;">
                                <span class="input-group-text">Latitude</span>
                                {{ form.latitude }}
                            </div>
                        """),
                        HTML("""
                            <div class="input-group ms-2" style="width: fit-content;">
                                <span class="input-group-text">Longitude</span>
                                {{ form.longitude }}
                            </div>
                        """),
                        css_class='d-flex align-items-center'
                    ),
                    HTML("""
                        <div class="text-center mt-2">
                            <i class="fas fa-map-marked-alt mx-1"></i>
                            <i class="fas fa-location-dot mx-1"></i>
                            <i class="fas fa-earth-americas mx-1"></i>
                            <i class="fas fa-map-location-dot mx-1"></i>
                            <i class="fas fa-compass mx-1"></i>
                        </div>
                    """),
                    css_class='col-auto'
                ),
                css_class='mb-3 justify-content-center'
            ),
            Div(
                HTML("""
                    <div id="place-form-map" 
                         class="map-container mb-3" 
                         style="height: 400px;">
                    </div>
                """),
                css_class='mb-3'
            ),
            Div(
                HTML("""
                    <div class="card mb-3">
                        <div class="card-header">
                            <h5 class="mb-0">Site Plan</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-12">
                                    {{ form.site_plan }}
                                    <div class="form-text">{{ form.site_plan.help_text }}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                """),
                *site_plan_layout,  # Include current site plan preview if it exists
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
        
        # Ensure site_plan is preserved
        if 'site_plan' in self.files:
            cleaned_data['site_plan'] = self.files['site_plan']
        
        return cleaned_data

    def clean_site_plan(self):
        site_plan = self.cleaned_data.get('site_plan')
        
        if site_plan:
            try:
                # Always reset to beginning
                site_plan.seek(0)
                
                img = Image.open(site_plan)
                
                # Basic dimension check
                if img.width < 200 or img.height < 200:
                    raise forms.ValidationError(
                        f'Image must be at least 200x200 pixels. '
                        f'Uploaded image is {img.width}x{img.height} pixels.'
                    )
                
                # Reset file pointer one final time
                site_plan.seek(0)
                return site_plan
                    
            except Exception as e:
                raise forms.ValidationError(f"Image validation failed: {str(e)}")
        
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
        self.place = initial.get('place')
        self.initial_location = initial.get('location')

        # Configure crispy form
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0'
        self.helper.form_show_errors = True
        self.helper.error_text_inline = False
        self.helper.help_text_inline = False
        
        # Configure location field
        if self.place:
            locations = Location.objects.filter(place=self.place).order_by('name')
            self.fields['location'].queryset = locations
            
            # Create standard choices tuple while adding data attributes to the widget
            choices = [(None, '---------')]
            attrs = {
                'class': 'form-select',
                'onchange': 'handleLocationChange(this)'
            }
            
            # Add data attributes to each option
            for location in locations:
                choices.append((location.pk, location.name))
                attrs[f'data-is-active-{location.pk}'] = str(location.is_active).lower()
            
            self.fields['location'].widget = forms.Select(attrs=attrs, choices=choices)
            
            if self.initial_location:
                self.fields['location'].initial = self.initial_location
                # If location is inactive, set device to inactive by default
                if not self.initial_location.is_active:
                    self.fields['is_active'].initial = False

        # Configure field labels and help text
        self.fields['is_active'].label = "Active"
        self.fields['device_type'].label = "Device Type"
        self.fields['location'].label = "Location"
        
        # Determine if new or existing
        is_new = not bool(kwargs.get('instance'))
        
        # Simple crispy layout using Bootstrap 5 grid
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-6'),
                Column('device_type', css_class='col-md-6'),
                css_class='mb-3'
            ),
            Row(
                Column('location', css_class='col-12'),
                css_class='mb-3'
            ),
            Row(
                Column('manufacturer', css_class='col-md-6'),
                Column('model', css_class='col-md-6'),
                css_class='mb-3'
            ),
            Row(
                Column('serial_number', css_class='col-12'),
                css_class='mb-3'
            ),
            Div(
                Row(
                    Column(
                        Div(
                            Field('is_active', wrapper_class='form-check'),
                            css_class='mb-1'
                        ),
                        Div(
                            HTML("""
                                <div id="device-status-warning" class="form-text text-warning" style="display: none;">
                                    <i class="bi bi-exclamation-triangle-fill me-1"></i>
                                    Device will be inactive as <i class="bi bi-geo-alt"></i> <span id="inactive-location-name"></span> is inactive
                                </div>
                            """),
                            css_class='small'
                        ),
                        css_class='col-auto'
                    ),
                    Column(
                        Div(
                            HTML("""
                                <a href="{% url 'sensors:place_detail' place_slug=place.slug %}"
                                   class="btn btn-outline-secondary">
                                    <i class="bi bi-x-lg me-1"></i>Cancel
                                </a>
                            """),
                            Submit(
                                'submit',
                                mark_safe('<i class="bi bi-hdd-rack me-1"></i>' + ('Create' if is_new else 'Save')),
                                css_class='btn btn-success ms-2'
                            ),
                            css_class='btn-group'
                        ),
                        css_class='col text-end'
                    ),
                    css_class='align-items-start'
                ),
                css_class='mt-4'
            ),
            HTML("""
                <script>
                function handleLocationChange(select) {
                    const selectedId = select.value;
                    const isActive = select.getAttribute(`data-is-active-${selectedId}`) === 'true';
                    const locationName = select.options[select.selectedIndex].text;
                    const checkbox = document.querySelector('#id_is_active');
                    const warning = document.querySelector('#device-status-warning');
                    const locationNameSpan = document.querySelector('#inactive-location-name');
                    
                    if (!isActive && selectedId) {
                        checkbox.checked = false;
                        checkbox.disabled = true;
                        warning.style.display = 'block';
                        locationNameSpan.textContent = locationName;
                    } else {
                        checkbox.disabled = false;
                        checkbox.checked = true;
                        warning.style.display = 'none';
                    }
                }
                
                // Initialize on page load
                document.addEventListener('DOMContentLoaded', function() {
                    const select = document.querySelector('#id_location');
                    if (select.value) {
                        handleLocationChange(select);
                    }
                });
                </script>
            """)
        )

        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.HiddenInput, forms.CheckboxInput)):
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        location = cleaned_data.get('location')
        is_active = cleaned_data.get('is_active')

        if location and not location.is_active and is_active:
            raise forms.ValidationError({
                'is_active': 'Device cannot be active when its location is inactive.'
            })
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

class LocationForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Location
        fields = ['name', 'is_active']

    def __init__(self, *args, **kwargs):
        # Get place from initial data or instance
        initial = kwargs.get('initial', {})
        instance = kwargs.get('instance')
        
        # Try to get place from initial data first, then from instance if available
        self.place = initial.get('place')
        if not self.place and instance:
            self.place = instance.place
            
        # Handle referrer
        referrer = kwargs.pop('referrer', None)
        super().__init__(*args, **kwargs)
        
        if not self.place:
            pass
        
        # Setup crispy form
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0'
        self.helper.form_id = 'locationForm'
        self.helper.form_show_errors = True
        self.helper.error_text_inline = False
        self.helper.help_text_inline = False
        
        if referrer:
            self.fields['referrer'].initial = referrer
        
        # Configure field properties
        self.fields['name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter location name',
            'minlength': '3',
        })
        
        self.fields['is_active'].label = ""  # Remove label since we use custom template
        self.fields['is_active'].help_text = None
        self.fields['is_active'].widget.attrs['class'] = 'form-check-input'
        
        # If place is inactive, force location to be inactive
        if self.place and not self.place.is_active:
            self.fields['is_active'].initial = False
            self.fields['is_active'].disabled = True
            self.fields['is_active'].help_text = "This location cannot be active because its place is inactive."
        
        # Custom layout with Bootstrap grid
        self.helper.layout = Layout(
            Field('referrer', type='hidden'),
            Row(
                Column('name', css_class='col-md-8'),
                Column(
                    Div(
                        Field(
                            'is_active',
                            template='sensors/includes/custom_switch.html'
                        ),
                        css_class='h-100 d-flex align-items-center justify-content-start'
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
        name = cleaned_data.get('name')
        is_active = cleaned_data.get('is_active')
        
        if name and len(name) < 3:
            self.add_error('name', 'Location name must be at least 3 characters long.')

        if not self.place:
            raise forms.ValidationError("Cannot create or edit a location without an associated place.")

        if self.place and not self.place.is_active and is_active:
            self.add_error('is_active', 'Location cannot be active when its place is inactive.')
            
        return cleaned_data 

class PlaceDeleteForm(forms.Form):
    confirm_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Type the place name here'
        })
    )

    def __init__(self, *args, place=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.place = place
        
        # Setup crispy form
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0'
        self.helper.form_show_errors = True
        self.helper.error_text_inline = False
        self.helper.help_text_inline = False
        
        # Custom layout
        self.helper.layout = Layout(
            # Warning about locations - add static-alert class
            HTML("""
                <div class="alert alert-warning mb-3 static-alert">
                    <i class="bi bi-exclamation-triangle"></i>
                    <strong>Warning:</strong> This will delete the following locations:
                    <div class="mt-2">
                        <ul class="mb-0">
                            {% for location in locations %}
                            <li>
                                <i class="bi bi-geo-alt"></i> {{ location.name }}
                                {% if location.active_devices_count or location.inactive_devices_count %}
                                ({{ location.active_devices_count|add:location.inactive_devices_count }} devices)
                                {% endif %}
                            </li>
                            {% endfor %}
                        </ul>
                    </div>
                </div>
            """),
            # Confirmation input - add static-alert class
            Div(
                HTML("""
                    <p class="mb-2">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        This action cannot be undone. Please type <strong>{{ place.name }}</strong> to confirm.
                    </p>
                """),
                Field('confirm_name'),
                css_class='alert alert-danger static-alert'
            ),
            # Buttons
            Div(
                HTML('<hr class="mt-4">'),
                Div(
                    HTML("""
                        <a href="{% url 'sensors:place_list' %}" 
                           class="btn btn-secondary">
                            <i class="bi bi-arrow-left"></i> Cancel
                        </a>
                    """),
                    HTML("""
                        <button type="submit" class="btn btn-danger">
                            <i class="bi bi-trash"></i> Delete
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
            raise forms.ValidationError(
                f'Confirmation name "{confirm_name}" does not match the place name "{self.place.name}". '
                'Please try again.'
            )
        return confirm_name