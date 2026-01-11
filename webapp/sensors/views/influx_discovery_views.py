"""
Views for InfluxDB sensor discovery.

Streamlined 2-step flow:
1. Select InfluxStore -> Discover all measurements and fields in one batch
2. Select fields -> Create sensors with initial cached values
"""
import json
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from icecream import ic

from ..models import Device, InfluxStore, Sensor, SensorType
from ..services.influx_discovery import (
    discover_all_fields,
    preview_measurement_field,
    get_latest_field_value,
    # Keep old functions for backward compatibility
    discover_measurements,
    discover_fields,
)
from .mixins import PlaceAnnotationMixin
from .influx_discovery_forms import InfluxStoreSelectionForm


class InfluxDiscoveryView(LoginRequiredMixin, PlaceAnnotationMixin, View):
    """Display the discovery modal with InfluxStore selector."""

    def get(self, request, place_slug, device_pk):
        place = self.get_place()
        device = get_object_or_404(Device, pk=device_pk, location__place=place)

        # Clear any existing session data for this device
        session_key = f'influx_discovery_{device_pk}'
        if session_key in request.session:
            del request.session[session_key]

        form = InfluxStoreSelectionForm(place=place)

        context = {
            'place': place,
            'device': device,
            'form': form,
            'modal_title': 'Discover Sensors from InfluxDB'
        }

        html = render_to_string('sensors/influx_discovery_modal.html', context, request=request)
        return HttpResponse(html)


class DiscoverAllFieldsView(LoginRequiredMixin, PlaceAnnotationMixin, View):
    """
    Streamlined discovery endpoint - discovers all measurements and fields
    in a single batch operation.
    """

    def post(self, request, place_slug, device_pk):
        place = self.get_place()
        device = get_object_or_404(Device, pk=device_pk, location__place=place)

        influx_store_id = request.POST.get('influx_store')
        if not influx_store_id:
            return HttpResponse(
                '<div class="alert alert-danger">Please select an InfluxDB store</div>',
                status=400
            )

        try:
            influx_store = get_object_or_404(InfluxStore, pk=influx_store_id, place=place)
        except Exception as e:
            return HttpResponse(
                f'<div class="alert alert-danger">Invalid InfluxStore: {e}</div>',
                status=400
            )

        # Get device_id for filtering
        device_id = device.device_id if device.device_id else None

        # Get existing sensors to mark as "already imported"
        existing_sensors = set(
            Sensor.objects.filter(
                device=device,
                influx_store=influx_store
            ).values_list('influx_measurement', 'influx_field_name')
        )

        # Batch discover all measurements and fields
        result = discover_all_fields(
            influx_store,
            device_id=device_id,
            existing_sensors=existing_sensors
        )

        if result['success']:
            # Count totals for display
            total_fields = sum(len(m['fields']) for m in result['measurements'])
            imported_count = sum(
                1 for m in result['measurements']
                for f in m['fields'] if f.get('imported')
            )

            context = {
                'measurements': result['measurements'],
                'influx_store': influx_store,
                'device': device,
                'place': place,
                'device_id': device_id,
                'total_measurements': len(result['measurements']),
                'total_fields': total_fields,
                'imported_count': imported_count,
            }
            html = render_to_string('sensors/partials/influx_field_tree.html', context, request=request)
            return HttpResponse(html)
        else:
            error_context = {
                'error': result.get('error', 'Unknown error'),
                'place': place,
                'device': device
            }
            error_html = render_to_string('sensors/partials/influx_error.html', error_context, request=request)
            return HttpResponse(error_html, status=500)


# Keep old views for backward compatibility but mark as deprecated
class DiscoverMeasurementsView(LoginRequiredMixin, PlaceAnnotationMixin, View):
    """DEPRECATED: Use DiscoverAllFieldsView instead."""

    def post(self, request, place_slug, device_pk):
        # Redirect to new unified view
        return DiscoverAllFieldsView.as_view()(request, place_slug=place_slug, device_pk=device_pk)


class DiscoverFieldsView(LoginRequiredMixin, PlaceAnnotationMixin, View):
    """DEPRECATED: Fields are now discovered in batch with measurements."""

    def post(self, request, place_slug, device_pk):
        # This view is kept for backward compatibility but redirects to the new flow
        return DiscoverAllFieldsView.as_view()(request, place_slug=place_slug, device_pk=device_pk)


class PreviewFieldView(LoginRequiredMixin, PlaceAnnotationMixin, View):
    """AJAX endpoint to preview sample data for a measurement+field."""

    def get(self, request, place_slug, device_pk):
        place = self.get_place()
        device = get_object_or_404(Device, pk=device_pk, location__place=place)

        influx_store_id = request.GET.get('influx_store')
        measurement = request.GET.get('measurement')
        field = request.GET.get('field')
        tag_key = request.GET.get('tag_key', 'device_id')

        if not influx_store_id or not measurement or not field:
            return HttpResponse('<div class="alert alert-danger">Missing required parameters</div>', status=400)

        try:
            influx_store = get_object_or_404(InfluxStore, pk=influx_store_id, place=place)
        except Exception as e:
            return HttpResponse(f'<div class="alert alert-danger">Invalid InfluxStore: {e}</div>', status=400)

        device_id = device.device_id if device.device_id else None
        result = preview_measurement_field(
            influx_store,
            measurement,
            field,
            device_id=device_id,
            tag_key=tag_key,
            limit=10
        )

        if result['success']:
            context = {
                'place': place,
                'device': device,
                'influx_store': influx_store,
                'measurement': measurement,
                'field': field,
                'tag_key': tag_key,
                'samples': result['samples']
            }
            html = render_to_string('sensors/partials/influx_preview_data.html', context, request=request)
            return HttpResponse(html)
        else:
            return HttpResponse(f'<div class="alert alert-warning">Error: {result.get("error", "Unknown error")}</div>', status=500)


class BulkCreateSensorsView(LoginRequiredMixin, PlaceAnnotationMixin, View):
    """
    Create multiple sensors from selected measurement+field combinations.

    Features:
    - Idempotent: skips existing sensors gracefully
    - Populates cached_reading_value on creation
    - Reports created vs skipped counts
    """

    def post(self, request, place_slug, device_pk):
        place = self.get_place()
        device = get_object_or_404(Device, pk=device_pk, location__place=place)

        influx_store_id = request.POST.get('influx_store')
        if not influx_store_id:
            return HttpResponse(
                '<div class="alert alert-danger">InfluxStore not specified</div>',
                status=400
            )

        try:
            influx_store = get_object_or_404(InfluxStore, pk=influx_store_id, place=place)
        except Exception as e:
            return HttpResponse(
                f'<div class="alert alert-danger">Invalid InfluxStore: {e}</div>',
                status=400
            )

        # Get selections from POST (new format: measurement:field:tag_key)
        selected_fields = request.POST.getlist('selected_fields')

        if not selected_fields:
            return HttpResponse(
                '<div class="alert alert-warning">No fields selected</div>',
                status=400
            )

        device_id = device.device_id if device.device_id else None

        created_sensors = []
        skipped_existing = []
        errors = []

        for selection in selected_fields:
            # Parse selection format: measurement|||field|||tag_key
            # Using ||| as delimiter to avoid conflicts with colons in measurement/field names
            parts = selection.split('|||')
            if len(parts) < 2:
                errors.append(f"Invalid selection format: {selection}")
                continue

            measurement = parts[0]
            field = parts[1]
            tag_key = parts[2] if len(parts) > 2 else 'device_id'
            sensor_name = f"{measurement} - {field}"

            # Check if sensor already exists (idempotent)
            existing = Sensor.objects.filter(
                device=device,
                influx_store=influx_store,
                influx_measurement=measurement,
                influx_field_name=field
            ).first()

            if existing:
                skipped_existing.append(sensor_name)
                continue

            # Try to match SensorType by field name or measurement
            sensor_type = SensorType.find_by_alias(field)
            if not sensor_type:
                sensor_type = SensorType.find_by_alias(measurement)

            try:
                # Create sensor
                sensor = Sensor.objects.create(
                    device=device,
                    name=sensor_name,
                    sensor_type=sensor_type,
                    influx_store=influx_store,
                    influx_measurement=measurement,
                    influx_field_name=field,
                    influx_tag_key=tag_key,
                    data_store='INFLUX',
                    is_active=device.is_active
                )

                # Fetch and populate initial cached value
                if device_id:
                    latest = get_latest_field_value(
                        influx_store,
                        measurement,
                        field,
                        device_id=device_id,
                        tag_key=tag_key
                    )

                    if latest['success'] and latest['value'] is not None:
                        sensor.cached_reading_value = latest['value']
                        sensor.cached_reading_timestamp = latest['timestamp']
                        sensor.cached_reading_source = 'influx_discovery'
                        sensor.last_cached_timestamp = timezone.now()
                        sensor.save(update_fields=[
                            'cached_reading_value',
                            'cached_reading_timestamp',
                            'cached_reading_source',
                            'last_cached_timestamp'
                        ])

                created_sensors.append({
                    'id': sensor.id,
                    'name': sensor.name,
                    'measurement': measurement,
                    'field': field
                })
            except Exception as e:
                errors.append(f"Error creating {sensor_name}: {str(e)}")

        # Build response message
        response = HttpResponse()
        triggers = {'closeModal': '#htmx-modal'}

        message_parts = []
        if created_sensors:
            message_parts.append(f"Created {len(created_sensors)} sensor{'s' if len(created_sensors) != 1 else ''}")
        if skipped_existing:
            message_parts.append(f"{len(skipped_existing)} already existed")
        if errors:
            message_parts.append(f"{len(errors)} error{'s' if len(errors) != 1 else ''}")

        if message_parts:
            message = ". ".join(message_parts) + "."
            msg_type = 'success'
            if errors and not created_sensors:
                msg_type = 'error'
            elif errors or skipped_existing:
                msg_type = 'warning' if created_sensors else 'info'

            triggers['showToast'] = {
                'message': message,
                'type': msg_type
            }

        response['HX-Trigger'] = json.dumps(triggers)

        # Redirect to device detail page
        from django.urls import reverse
        device_url = reverse('sensors:device_detail', kwargs={
            'place_slug': place.slug,
            'pk': device.pk
        })
        response['HX-Redirect'] = device_url

        return response
