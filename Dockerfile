# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY orchestrator/ ./orchestrator/
COPY config/ ./config/

# Set Python path and environment variables
ENV PYTHONPATH=/app
ENV PORT=8080

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Run FastAPI application (stateless, no worker processes needed)
CMD ["uvicorn", "orchestrator.app_unified:app", "--host", "0.0.0.0", "--port", "8080"]
