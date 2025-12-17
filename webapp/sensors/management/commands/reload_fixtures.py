"""
Management command to reload fixture data for system records.

This command updates system seed data (pk < 100) from YAML fixtures while
preserving user-created (pk 100-999) and auto-created (pk >= 1000) records.

Usage:
    ./manage.py reload_fixtures                    # Reload all fixtures
    ./manage.py reload_fixtures --types            # Reload sensor_types only
    ./manage.py reload_fixtures --units            # Reload units only
    ./manage.py reload_fixtures --devices          # Reload device_types only
    ./manage.py reload_fixtures --dry-run          # Show what would be updated
    ./manage.py reload_fixtures --force            # Update even if record was modified
"""
import yaml
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sensors.models import SensorType, DeviceType, Unit


class Command(BaseCommand):
    help = 'Reload system fixture data (pk < 100) from YAML files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--types',
            action='store_true',
            help='Reload sensor_types.yaml only',
        )
        parser.add_argument(
            '--units',
            action='store_true',
            help='Reload units.yaml only',
        )
        parser.add_argument(
            '--devices',
            action='store_true',
            help='Reload device_types.yaml only',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even for records that may have been modified',
        )

    def handle(self, *args, **options):
        fixtures_dir = Path(__file__).resolve().parent.parent.parent / 'fixtures'

        dry_run = options['dry_run']
        force = options['force']

        # Determine which fixtures to reload
        reload_all = not (options['types'] or options['units'] or options['devices'])

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made\n'))

        try:
            with transaction.atomic():
                if reload_all or options['units']:
                    self._reload_units(fixtures_dir / 'units.yaml', dry_run, force)

                if reload_all or options['types']:
                    self._reload_sensor_types(fixtures_dir / 'sensor_types.yaml', dry_run, force)

                if reload_all or options['devices']:
                    self._reload_device_types(fixtures_dir / 'device_types.yaml', dry_run, force)

                if dry_run:
                    # Rollback the transaction for dry run
                    raise DryRunComplete()

        except DryRunComplete:
            self.stdout.write(self.style.WARNING('\nDry run complete - no changes made'))

        if not dry_run:
            self.stdout.write(self.style.SUCCESS('\nFixture reload complete!'))

    def _reload_units(self, filepath, dry_run, force):
        self.stdout.write(self.style.HTTP_INFO(f'\n=== Reloading Units from {filepath.name} ==='))

        if not filepath.exists():
            raise CommandError(f'Fixture file not found: {filepath}')

        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)

        units_data = data.get('units', [])
        created, updated, skipped = 0, 0, 0

        for item in units_data:
            pk = item['id']
            if pk >= 100:
                self.stdout.write(f'  Skipping pk={pk} (not a system record)')
                skipped += 1
                continue

            defaults = {
                'name': item['name'],
                'symbol': item.get('symbol', ''),
                'is_system': True,
            }

            try:
                existing = Unit.objects.get(pk=pk)
                # Check what changed
                changes = self._get_changes(existing, defaults)
                if changes:
                    if not dry_run:
                        for field, value in defaults.items():
                            setattr(existing, field, value)
                        existing.save()
                    self.stdout.write(f'  Updated Unit pk={pk} "{item["name"]}": {changes}')
                    updated += 1
                else:
                    skipped += 1
            except Unit.DoesNotExist:
                if not dry_run:
                    Unit.objects.create(pk=pk, **defaults)
                self.stdout.write(self.style.SUCCESS(f'  Created Unit pk={pk} "{item["name"]}"'))
                created += 1

        self.stdout.write(f'  Summary: {created} created, {updated} updated, {skipped} unchanged')

    def _reload_sensor_types(self, filepath, dry_run, force):
        self.stdout.write(self.style.HTTP_INFO(f'\n=== Reloading Sensor Types from {filepath.name} ==='))

        if not filepath.exists():
            raise CommandError(f'Fixture file not found: {filepath}')

        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)

        types_data = data.get('sensor_types', [])
        created, updated, skipped = 0, 0, 0

        for item in types_data:
            pk = item['id']
            if pk >= 100:
                self.stdout.write(f'  Skipping pk={pk} (not a system record)')
                skipped += 1
                continue

            # Get unit reference
            unit = None
            if item.get('unit_id'):
                try:
                    unit = Unit.objects.get(pk=item['unit_id'])
                except Unit.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f'  Warning: Unit pk={item["unit_id"]} not found for SensorType "{item["name"]}"'
                    ))

            defaults = {
                'name': item['name'],
                'description': item.get('description', ''),
                'unit': unit,
                'graph_type': item.get('graph_type', 'LINE'),
                'decimal_places': item.get('decimal_places', 2),
                'min_value': item.get('min_value'),
                'max_value': item.get('max_value'),
                'allow_override': item.get('allow_override', False),
                'aliases': item.get('aliases', []),
                'influx_measurement': item.get('influx_measurement'),
                'influx_field_name': item.get('influx_field_name'),
                'is_system': True,
            }

            try:
                existing = SensorType.objects.get(pk=pk)
                changes = self._get_changes(existing, defaults)
                if changes:
                    if not dry_run:
                        for field, value in defaults.items():
                            setattr(existing, field, value)
                        existing.save()
                    self.stdout.write(f'  Updated SensorType pk={pk} "{item["name"]}": {changes}')
                    updated += 1
                else:
                    skipped += 1
            except SensorType.DoesNotExist:
                if not dry_run:
                    SensorType.objects.create(pk=pk, **defaults)
                self.stdout.write(self.style.SUCCESS(f'  Created SensorType pk={pk} "{item["name"]}"'))
                created += 1

        self.stdout.write(f'  Summary: {created} created, {updated} updated, {skipped} unchanged')

    def _reload_device_types(self, filepath, dry_run, force):
        self.stdout.write(self.style.HTTP_INFO(f'\n=== Reloading Device Types from {filepath.name} ==='))

        if not filepath.exists():
            raise CommandError(f'Fixture file not found: {filepath}')

        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)

        types_data = data.get('device_types', [])
        created, updated, skipped = 0, 0, 0

        for item in types_data:
            pk = item['id']
            if pk >= 100:
                self.stdout.write(f'  Skipping pk={pk} (not a system record)')
                skipped += 1
                continue

            defaults = {
                'name': item['name'],
                'description': item.get('description', ''),
                'icon': item.get('icon', 'bi-device'),
                'aliases': item.get('aliases', []),
                'is_system': True,
            }

            try:
                existing = DeviceType.objects.get(pk=pk)
                changes = self._get_changes(existing, defaults)
                if changes:
                    if not dry_run:
                        for field, value in defaults.items():
                            setattr(existing, field, value)
                        existing.save()
                    self.stdout.write(f'  Updated DeviceType pk={pk} "{item["name"]}": {changes}')
                    updated += 1
                else:
                    skipped += 1
            except DeviceType.DoesNotExist:
                if not dry_run:
                    DeviceType.objects.create(pk=pk, **defaults)
                self.stdout.write(self.style.SUCCESS(f'  Created DeviceType pk={pk} "{item["name"]}"'))
                created += 1

        self.stdout.write(f'  Summary: {created} created, {updated} updated, {skipped} unchanged')

    def _get_changes(self, instance, defaults):
        """Compare instance fields with defaults and return list of changed fields."""
        changes = []
        for field, new_value in defaults.items():
            current_value = getattr(instance, field, None)
            # Handle ForeignKey comparison
            if hasattr(current_value, 'pk'):
                current_value = current_value if current_value else None
                if current_value != new_value:
                    changes.append(field)
            elif current_value != new_value:
                changes.append(field)
        return changes


class DryRunComplete(Exception):
    """Raised to rollback transaction during dry run."""
    pass
