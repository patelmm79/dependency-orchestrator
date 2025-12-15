# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including supervisor for multi-process)
RUN apt-get update && apt-get install -y \
    git \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create supervisor directories
RUN mkdir -p /var/log/supervisor /var/run

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY orchestrator/ ./orchestrator/
COPY config/ ./config/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Set Python path and environment variables
ENV PYTHONPATH=/app
ENV PORT=8080
ENV REDIS_URL=redis://localhost:6379/0

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Run supervisor to manage web + worker processes
# In Cloud Run, REDIS_URL should point to Redis Memorystore
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
