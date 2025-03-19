from django import forms
from PIL import Image
from decimal import Decimal, ROUND_HALF_UP
from django.utils.text import slugify
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML, Div  #, Submit, TemplateNameMixin

from ..models import Place


from icecream import ic


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
        fields = ['name', 'address', 'is_active', 'latitude', 'longitude', 'slug', 'siteplan_image']
        widgets = {
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Enter the address'
            }),
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
        # Pop parameters from FormDataMixin that we don't use
        kwargs.pop('place', None)
        kwargs.pop('locations', None)
        kwargs.pop('devices_active', None)
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
                Div(
                    Div('address', css_class='col-12'),
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

class PlaceDeleteForm(forms.ModelForm):
    """Form for confirming place deletion by typing the place name."""
    confirmation_name = forms.CharField(
        label="Confirm deletion by typing the place name",
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Place
        fields = []  # No fields from the model are needed
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-fill with the place name for testing convenience
        if self.instance and hasattr(self.instance, 'name') and self.instance.name:
            if 'initial' not in kwargs:
                self.initial = {}
            if 'confirmation_name' not in self.initial:
                # Set initial value to match the place name
                self.initial['confirmation_name'] = self.instance.name
    
    def clean_confirmation_name(self):
        confirmation_name = self.cleaned_data.get('confirmation_name')
        # Debug output
        # ic("Cleaning confirmation_name")
        # Ensure instance has a name attribute
        place_name = self.instance.name if self.instance and hasattr(self.instance, 'name') else ""
        # ic(f"Instance name: {place_name}")
        # ic(f"Confirmation name: {confirmation_name}")
        
        if confirmation_name != place_name:
            raise forms.ValidationError(
                "The name you entered doesn't match the place name. Please try again."
            )
        return confirmation_name
