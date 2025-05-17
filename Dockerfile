FROM python:3.9-slim

WORKDIR /app

# Add build argument for collectstatic
ARG SKIP_COLLECTSTATIC=1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.4.2 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    DJANGO_SETTINGS_MODULE=backend.settings.prod

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        libpq-dev \
        netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
ENV PATH="${POETRY_HOME}/bin:$PATH"

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-root --no-dev --no-interaction

# Copy project files
COPY . .

# Copy build-time environment variables
COPY .env.build .env

# Set required environment variables for collectstatic
ENV REDIS_URL=redis://redis:6379/0 \
    DATABASE_URL=postgres://postgres:postgres@db:5432/postgres \
    SECRET_KEY=dummy-key-for-build \
    DEBUG=False

# Collect static files only if SKIP_COLLECTSTATIC is not set to 1
RUN if [ "$SKIP_COLLECTSTATIC" = "0" ]; then \
        python manage.py collectstatic --noinput; \
    fi

# Remove build-time environment file
RUN rm .env

# Create entrypoint script
RUN echo '#!/bin/sh\nset -e\npython manage.py migrate\nexec gunicorn --bind 0.0.0.0:8000 backend.wsgi:application' > /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"] 