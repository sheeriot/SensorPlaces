# Reload all fixtures (units, sensor_types, device_types)
./manage.py reload_fixtures

# Reload specific fixtures only
./manage.py reload_fixtures --types      # sensor_types.yaml only
./manage.py reload_fixtures --units      # units.yaml only
./manage.py reload_fixtures --devices    # device_types.yaml only

# Preview changes without applying
./manage.py reload_fixtures --dry-run

# Force update (for future use)
./manage.py reload_fixtures --force
