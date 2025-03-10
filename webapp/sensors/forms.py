from django import forms
from .models import Sensor, InfluxSource, Place, Device, Location
from PIL import Image
from decimal import Decimal, ROUND_HALF_UP
from django.utils.text import slugify
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML, Div, Submit, TemplateNameMixin
from crispy_forms.bootstrap import PrependedText, FormActions
from django.db import models
from icecream import ic
from django.db.models import Count, Q


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
        # setup Active field
        # if self.instance and self.instance.is_active:
        #     self.fields['is_active'].label = mark_safe("""
        #         <span class="badge ms-1 bg-success-subtle text-success">
        #             Active
        #         </span>
        #     """)
        # else:
        #     self.fields['is_active'].label = mark_safe("""
        #         <span class="badge ms-1 bg-secondary-subtle text-secondary">
        #             inactive
        #         </span>
        #     """)
        
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
            Row(
                Column('name', css_class='col-md-8'),
                Column(
                    Div(
                        Field(
                            'is_active',
                            template='sensors/partials/custom_switch.html'
                        ),
                        css_class='d-flex align-items-center h-100'
                    ),
                    css_class='col-md-4'
                ),
                css_class='mb-3'
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

class DeviceForm(forms.ModelForm):
    referrer = forms.CharField(widget=forms.HiddenInput(), required=False)

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
        # Get referrer from kwargs before calling super
        referrer = kwargs.pop('referrer', None)
        # Get place from kwargs before calling super
        self.place = kwargs.pop('place', None)
        self.initial_location = kwargs.pop('initial_location', None)
        
        # Debug initialization parameters
        ic("DeviceForm - Init:", {
            'place': self.place.name if self.place else None,
            'initial_location': self.initial_location.name if self.initial_location else None,
            'has_instance': bool(kwargs.get('instance')),
            'instance_location': kwargs.get('instance').location.name if kwargs.get('instance') else None
        })
        
        super().__init__(*args, **kwargs)
        
        # Configure location field based on place
        if self.place:
            # Get locations from the place - these will already be annotated by LocationAnnotationMixin
            locations_qs = Location.objects.filter(
                place=self.place
            ).annotate(
                active_devices_count=Count('devices', filter=Q(devices__is_active=True))
            ).order_by('-is_active', 'name')
            
            # Debug available locations
            ic("DeviceForm - Locations:", {
                'count': locations_qs.count(),
                'locations': [(loc.pk, loc.name, loc.is_active, loc.active_devices_count) for loc in locations_qs]
            })
            
            # Create standard choices tuple with data attributes
            attrs = {
                'class': 'form-select',
            }
            
            # Add data attributes for each location's active status
            for location in locations_qs:
                attrs[f'data-is-active-{location.pk}'] = str(location.is_active).lower()
            
            # Create custom choices with status and device counts
            choices = []
            for location in locations_qs:
                if location.is_active:
                    label = f"{location.name} ({location.active_devices_count} active)"
                else:
                    label = f"{location.name} (inactive)"
                choices.append((location.pk, label))
            
            # Set the queryset and custom widget
            self.fields['location'].queryset = locations_qs
            self.fields['location'].widget = forms.Select(
                attrs=attrs,
                choices=[('', '---------')] + choices
            )
            
            # Only set initial location if this is an existing device
            if self.instance and self.instance.pk:
                ic("DeviceForm - Setting instance location:", {
                    'location': self.instance.location.name,
                    'location_id': self.instance.location.pk
                })
                self.fields['location'].initial = self.instance.location

        # Configure field labels and help text
        self.fields['is_active'].label = "Active"
        self.fields['is_active'].help_text = ""
        self.fields['device_type'].label = "Device Type"
        self.fields['location'].label = "Location"
        
        # Debug final form state
        ic("DeviceForm - Final State:", {
            'location_initial': self.fields['location'].initial.pk if self.fields['location'].initial else None,
            'location_choices': list(self.fields['location'].choices),
        })

        # Configure crispy form helper
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0'
        self.helper.form_show_errors = True
        self.helper.error_text_inline = True
        self.helper.help_text_inline = True
        self.helper.form_id = 'device-form'

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
            Row(
                Column(
                    Div(
                        Div(
                            Field('is_active', wrapper_class='form-check form-switch'),
                            HTML("""
                                <small id="device-help-inactive" class="form-text text-muted ms-3" style="display: none;">
                                    Device cannot be active when its location is inactive
                                </small>
                            """),
                            css_class='d-flex align-items-center'
                        ),
                        css_class='d-flex'
                    ),
                    css_class='col-md-12'
                ),
                css_class='mb-3'
            ),
            Field('referrer', type='hidden'),
            Div(
                HTML('<hr class="mt-3">'),
                Div(
                    HTML("""
                        <a href="{{ form.referrer.value|default:'' }}" 
                           class="btn btn-outline-secondary">
                            <i class="bi bi-x-lg me-1"></i>Cancel
                        </a>
                    """),
                    HTML("""
                        <button type="submit" class="btn btn-success">
                            <i class="bi bi-hdd-rack me-1"></i>{% if not instance.pk %}Create{% else %}Save{% endif %}
                        </button>
                    """),
                    css_class='d-flex justify-content-between align-items-center'
                ),
                css_class='mt-3'
            ),
            HTML("""
                <script>
                document.addEventListener('DOMContentLoaded', function() {
                    // Get the form element
                    const form = document.getElementById('device-form');
                    
                    // Scope all queries to this form
                    const locationSelect = form.querySelector('#id_location');
                    const deviceActiveSwitch = form.querySelector('#id_is_active');
                    const helpText = form.querySelector('#device-help-inactive');
                    
                    function handleLocationChange(select) {
                        // Get the selected option
                        const selectedOption = select.options[select.selectedIndex];
                        // Get the location's active status from data attribute
                        const locationId = selectedOption.value;
                        const isActive = select.getAttribute(`data-is-active-${locationId}`) === 'true';
                        
                        // Update device active switch
                        if (!isActive && deviceActiveSwitch.checked) {
                            deviceActiveSwitch.checked = false;
                        }
                        deviceActiveSwitch.disabled = !isActive;
                        
                        // Update help text visibility
                        if (!isActive) {
                            helpText.textContent = "Device cannot be active when its location is inactive";
                            helpText.style.display = 'block';
                        } else {
                            helpText.style.display = 'none';
                        }
                    }
                    
                    // Set initial state
                    if (locationSelect) {
                        handleLocationChange(locationSelect);
                        // Add change listener
                        locationSelect.addEventListener('change', function() {
                            handleLocationChange(this);
                        });
                    }
                });
                </script>
            """)
        )

    def clean(self):
        cleaned_data = super().clean()
        location = cleaned_data.get('location')
        is_active = cleaned_data.get('is_active')

        if not location:
            self.add_error('location', 'Please select a location for the device.')
            return cleaned_data

        # Ensure location belongs to the correct place
        if self.place and location.place != self.place:
            self.add_error('location', 'Selected location does not belong to the current place.')
        
        # Validate active status based on location
        if location and not location.is_active and is_active:
            self.add_error('is_active', 'Device cannot be active when its location is inactive.')
        
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
    referrer = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    place_id = forms.ModelChoiceField(
        queryset=Place.objects.all(),
        widget=forms.HiddenInput()
    )
    
    # Display-only field for place name
    place_name = forms.CharField(
        label='Place',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control-plaintext fs-5 fw-medium',
            'readonly': True
        })
    )

    class Meta:
        model = Location
        fields = ['name', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get place from initial data or instance
        self.place = None
        if 'initial' in kwargs and 'place' in kwargs['initial']:
            self.place = kwargs['initial']['place']
        elif self.instance and self.instance.pk:
            self.place = self.instance.place

        self.fields['place_id'].initial = self.place
        self.fields['place_name'].initial = self.place.name

        # Add inactive styling if place is not active
        if not self.place.is_active:
            self.fields['place_name'].widget.attrs.update({
                'class': 'form-control-plaintext fs-5 fw-medium text-muted opacity-50'
            })
        if self.place.is_active:
            self.fields['place_name'].label = mark_safe("""Place
                <span class="badge ms-1 bg-success-subtle text-success">
                    Active
                </span>
            """)
        else:
            self.fields['place_name'].label = mark_safe("""Place
                <span class="badge ms-1 bg-secondary-subtle text-secondary">
                    inactive
                </span>
            """)

        # Configure field properties
        self.fields['is_active'].label = "Active"
        self.fields['is_active'].help_text = None

        # Setup crispy form
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_method = 'post'
        self.helper.form_class = 'mb-0'

        # Update the layout to use referrer for cancel button
        self.helper.layout = Layout(
            Field('referrer', type='hidden'),
            Field('place_id', type='hidden'),
            Row(
                Column(
                    Field('name'),
                    css_class='col-md-7'
                ),
                Column(
                    Div(
                        Div(
                            HTML('<i class="bi bi-house-gear me-1"></i>'),
                            Field(
                                'place_name',
                                css_class='form-control-plaintext px-0'
                            ),
                            css_class='d-flex align-items-center'
                        ),
                        css_class='w-100'
                    ),
                    css_class='col-md-5'
                ),
                css_class='mb-2'
            ),
            Row(
                Column(
                    Div(
                        Field(
                            'is_active',
                            template='sensors/partials/custom_switch.html'
                        ),
                        css_class='d-flex align-items-center'
                    ),
                    css_class='col-md-4'
                ),
                css_class='mb-2'
            ),
            Div(
                HTML('<hr class="mt-3">'),
                Div(
                    HTML("""
                        <a href="{{ form.referrer.value|default:'' }}" 
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
        cleaned_data['place'] = cleaned_data.pop('place_id')
        
        if self.instance and self.instance.pk:
            if cleaned_data.get('place') != self.instance.place:
                raise forms.ValidationError("The place field cannot be modified after creation.")
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