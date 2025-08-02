"""
Gunicorn configuration file for SensorPlaces
"""

import multiprocessing
import os

# The number of worker processes for handling requests
workers = int(os.environ.get('WORKERS', multiprocessing.cpu_count() * 2 + 1))

# The socket to bind
bind = "0.0.0.0:8002"

# Whether to print verbose debug output
debug = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'

# Maximum number of simultaneous clients
max_requests = 1000

# Restart workers after so many requests to free memory
max_requests_jitter = 50

# Timeout for requests
timeout = 30

# Logging settings
errorlog = '-'
accesslog = '-'
loglevel = 'info'

# Keep the workers alive for so many seconds
keepalive = 2 