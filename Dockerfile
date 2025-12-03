# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY orchestrator/ ./orchestrator/
COPY config/ ./config/

# Set Python path
ENV PYTHONPATH=/app

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Run the application
CMD exec uvicorn orchestrator.app:app --host 0.0.0.0 --port ${PORT:-8080}
