#!/bin/bash

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="/root/.local/bin:$PATH"

# Configure Poetry
poetry config virtualenvs.create false

# Install dependencies
poetry install --no-dev

# Collect static files
poetry run python manage.py collectstatic --noinput