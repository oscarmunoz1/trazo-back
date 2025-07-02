FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create static directory
RUN mkdir -p /app/staticfiles

# Expose port (Railway will override this with $PORT)
EXPOSE 8000

# Start command - CRITICAL: Use $PORT not hardcoded 8000
# Move collectstatic to runtime when env vars are available
CMD python manage.py migrate --settings=backend.settings.prod && \
    python manage.py collectstatic --noinput --settings=backend.settings.prod && \
    gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --log-level debug 