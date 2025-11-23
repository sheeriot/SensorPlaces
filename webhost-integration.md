# Integrating SensorPlaces with Webhost NGINX Setup

This guide provides instructions on how to integrate the SensorPlaces Docker Compose setup with the webhost NGINX configuration.

## Prerequisites

- SensorPlaces Docker Compose setup running
- Webhost NGINX Docker Compose setup running

## Steps to Integrate

1. Ensure both the webhost and SensorPlaces projects are in the same Docker network (named "webhost" as defined in the `docker-compose.yml`).

2. In the webhost project, add a new NGINX server block configuration file for SensorPlaces:

Create a file `resources/nginx/conf.d/sensorplaces.conf` in your webhost repository:

```nginx
server {
    listen 80;
    server_name sensorplaces.yourdomain.com;

    location / {
        proxy_pass http://sensorplaces:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /static/;
    }

    location /media/ {
        alias /media/;
    }
}
```

3. For HTTPS support, update your webhost's Docker Compose file to mount the SensorPlaces static and media volumes:

Add to the appropriate NGINX service in `docker-compose.yml`:

```yaml
volumes:
  # Existing volumes...
  - sensorplaces_sensorplaces-static:/static
  - sensorplaces_sensorplaces-media:/media
```

4. Update the HTTP to HTTPS redirect in webhost if needed.

5. If you're using Let's Encrypt for SSL certificates, make sure to add the domain to your certificate request.

## Using HTTPS Server Block

For HTTPS, your NGINX configuration should include:

```nginx
server {
    listen 443 ssl;
    server_name sensorplaces.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://sensorplaces:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /static/;
    }

    location /media/ {
        alias /media/;
    }
}

# HTTP to HTTPS redirect
server {
    listen 80;
    server_name sensorplaces.yourdomain.com;
    return 301 https://$host$request_uri;
}
```

## Restart Services

After making these changes, restart the webhost services:

```bash
cd /path/to/webhost
docker-compose down
docker-compose up -d
```
