# Use Python 3.12 slim for smaller image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create data directory if not exists
RUN mkdir -p /app/data /app/db

# Persistent volume setup will be handled in fly.toml
# Move the DB to the db folder and create a symlink if necessary
# or just ensure DatabaseManager points to /app/db/quantiprobot.db

# Command to run
# Copy and prepare start script
COPY start.sh .
RUN chmod +x start.sh

# Command to run (Use start script to launch both API and Bot)
CMD ["./start.sh"]
