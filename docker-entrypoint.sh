#!/bin/bash
set -e

# Wait for the database to be ready
# Note: This is a simple loop. For production, a more robust solution like wait-for-it.sh is recommended.
# echo "Waiting for database..."
# while ! nc -z db 5432; do
#   sleep 1
# done
# echo "Database is ready."

# Apply database migrations
echo "Apply database migrations"
python manage.py migrate --verbosity 1

# Collect static files
echo "Collect static files"
python manage.py collectstatic --noinput --verbosity 1

# Create superuser if needed (requires environment variables)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
  echo "Creating superuser..."
  python manage.py createsuperuser --noinput
fi

# Execute the command passed to the script
echo "Executing command: $@"
exec "$@" 