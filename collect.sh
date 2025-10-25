#!/bin/bash
docker compose exec sensors ./manage.py collectstatic --noinput

