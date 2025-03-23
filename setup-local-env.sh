#!/bin/bash

# Check if file exists and if not, create it
if [ ! -f "./env/django.env" ]; then
    echo "Creating django.env from sample..."
    cp env/django-sample.env env/django.env
    echo "Local environment file created."
else
    echo "env/django.env already exists. Skipping."
fi

# Make the file executable
chmod +x ./docker-entrypoint.sh

echo "Setup complete. You can now run 'docker-compose up' to start the application." 