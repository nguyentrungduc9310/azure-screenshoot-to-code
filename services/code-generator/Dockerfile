# Code Generator Service Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gcc \
        g++ \
        && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Copy requirements and install Python dependencies
COPY --chown=app:app requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy shared modules
COPY --chown=app:app shared/ shared/

# Copy application code
COPY --chown=app:app app/ app/

# Add user pip to PATH
ENV PATH="/home/app/.local/bin:${PATH}"

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health/live || exit 1

# Expose port
EXPOSE 8002

# Start command
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]