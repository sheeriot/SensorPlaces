#!/usr/bin/env python
"""
Generate fixture data for testing.

This script creates fixture files from the live database for use in tests.
Run this script from the project root directory:

python sensors/tests/generate_fixtures.py

"""

import os
import sys
import django
import subprocess
from pathlib import Path

# Add the project root directory to the Python path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sensorplaces.settings')
django.setup()

# Define the fixture directory
FIXTURE_DIR = BASE_DIR / 'sensors' / 'tests' / 'fixtures'

# Ensure the fixture directory exists
FIXTURE_DIR.mkdir(exist_ok=True)

# Define the models to export
FIXTURES = [
    ('auth.User', 'test_users.json'),
    ('sensors.Place', 'test_places.json'),
    ('sensors.Location', 'test_locations.json'),
    ('sensors.Device', 'test_devices.json'),
    ('sensors.Sensor', 'test_sensors.json'),
    ('sensors.SensorReading', 'test_readings.json'),
]

def generate_fixtures():
    """Generate fixture files from the database."""
    print("Generating fixture files...")

    for model, filename in FIXTURES:
        output_path = FIXTURE_DIR / filename
        cmd = [
            'python', 'manage.py', 'dumpdata',
            model,
            '--indent', '2',
            '-o', str(output_path)
        ]

        try:
            subprocess.run(cmd, check=True)
            print(f"✅ Created {filename}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating {filename}: {e}")

    print("\nFixture generation complete!")
    print(f"Fixtures saved to: {FIXTURE_DIR}")
    print("\nTo use these fixtures in your tests, add them to your TestCase class:")
    print("""
    class YourTestCase(TestCase):
        fixtures = [
            'test_users.json',
            'test_places.json',
            'test_locations.json',
            'test_devices.json',
            'test_sensors.json',
            'test_readings.json',
        ]
    """)

if __name__ == '__main__':
    generate_fixtures()
