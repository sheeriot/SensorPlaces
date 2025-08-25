FROM python:3.12-slim-bookworm

ARG UID=1000
ARG GID=1000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create a non-root user and group
RUN groupadd -g "${GID}" -r web \
    && useradd -d '/opt/app' -g web -l -r -u "${UID}" web

# Create app directories and set permissions
RUN mkdir -p /opt/app/db \
    && mkdir -p /opt/app/static_files \
    && mkdir -p /opt/app/media \
    && mkdir -p /opt/app/webapp \
    && chown -R web:web /opt/app

# Switch to the non-root user
USER web
WORKDIR /opt/app

# Set up virtual environment as the web user
ENV VIRTUAL_ENV=/opt/app/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install requirements into the venv as the web user
COPY --chown=web:web requirements.txt .
RUN pip install -r requirements.txt

# Copy application code as the web user
COPY --chown=web:web webapp ./webapp
COPY --chown=web:web docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Set final workdir
WORKDIR /opt/app/webapp

 