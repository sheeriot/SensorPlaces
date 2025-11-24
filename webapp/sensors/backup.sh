#!/bin/bash
set -euo pipefail

# This script backups the sqlite3 database by finding the docker volume
# on the host system and copying the database file directly.
# This method requires 'sudo' to access the Docker volume data area.

# Configuration
BACKUP_DIR="backups" # Directory to store backups, relative to the script location.
# Docker composes uses the directory name as the project name by default.
PROJECT_NAME=$(basename "$PWD")
VOLUME_NAME="${PROJECT_NAME}_sensorplaces-db" # Volume name from docker-compose.yml
DB_FILENAME="db.sqlite3" # Filename from env/django.env

# --- Script ---

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILENAME="sensorplaces-db-backup-${TIMESTAMP}.sqlite3"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

echo "Creating backup directory..."
mkdir -p "${BACKUP_DIR}"

echo "Inspecting volume '${VOLUME_NAME}' to find the host mount point..."
# Using grep and awk to parse the JSON output of 'docker volume inspect'
VOLUME_MOUNT_POINT=$(docker volume inspect "${VOLUME_NAME}" | grep '"Mountpoint":' | awk -F'"' '{print $4}')

if [ -z "${VOLUME_MOUNT_POINT}" ]; then
    echo "Error: Could not find mount point for volume '${VOLUME_NAME}'." >&2
    echo "Hint: Is the docker-compose stack running?" >&2
    exit 1
fi

DB_SOURCE_PATH="${VOLUME_MOUNT_POINT}/${DB_FILENAME}"

echo "Checking for database file at: ${DB_SOURCE_PATH}"
# We need sudo to check if the file exists in the docker volume directory
if ! sudo test -f "${DB_SOURCE_PATH}"; then
    echo "Error: Database file not found at '${DB_SOURCE_PATH}'" >&2
    exit 1
fi

echo "Copying database from host volume to ${BACKUP_PATH}..."
# The volume data directory is owned by root, so we need sudo to copy from it.
sudo cp "${DB_SOURCE_PATH}" "${BACKUP_PATH}"

echo "Setting ownership of backup file..."
sudo chown "$(id -u):$(id -g)" "${BACKUP_PATH}"

echo "Backup complete!"
echo "Backup file is located at: ${BACKUP_PATH}"

# --- Optional: Clean up old backups ---
# This will remove all but the 5 most recent backups.
# Uncomment the following line to enable cleanup.
# find "${BACKUP_DIR}" -name "sensorplaces-db-backup-*.sqlite3" -type f | sort -r | tail -n +6 | xargs -r rm --

echo "Done."
