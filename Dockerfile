FROM python:3.12-slim-bookworm 

ARG UID=1000 \
    GID=1000

# container ENV settings
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install requirements
COPY requirements.txt /opt/app/
RUN pip install -r /opt/app/requirements.txt
RUN echo "CACHE_VERSION=$(date +%s)" >> /etc/environment

## mount points
RUN mkdir -p /opt/app/db
RUN mkdir -p /opt/app/static_files
RUN mkdir -p /opt/app/media

# App Code directory
RUN mkdir -p /opt/app/webapp/

# setup files
COPY docker-entrypoint.sh /opt/app/
RUN chmod +x /opt/app/docker-entrypoint.sh

# copy the app code
COPY webapp /opt/app/webapp/

# create user to run the apps
RUN groupadd -g "${GID}" -r web \
  && useradd -d '/opt/app' -g web -l -r -u "${UID}" web \
  && chown web:web -R '/opt/app'

# switch to non-root user
USER web

# home for the app
WORKDIR /opt/app/webapp

 