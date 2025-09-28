# Multi-stage Docker build for Image Processor Service

# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies for image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime dependencies for image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libjpeg62-turbo \
    libpng16-16 \
    libtiff6 \
    libfreetype6 \
    liblcms2-2 \
    libwebp7 \
    libharfbuzz0b \
    libfribidi0 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser shared/ ./shared/

# Create temp directory for image processing
RUN mkdir -p /tmp/image_processing && chown appuser:appuser /tmp/image_processing

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH=/home/appuser/.local/bin:$PATH
ENV TMPDIR=/tmp/image_processing

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Start application
CMD ["python", "-m", "app.main"]