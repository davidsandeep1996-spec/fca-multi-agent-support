# ============================================================================
# STAGE 1: Base
# ============================================================================

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create app user (don't run as root)
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# ============================================================================
# STAGE 2: Dependencies
# ============================================================================

FROM base as dependencies

# Copy requirements
COPY requirements.txt .

# 1. Upgrade pip
RUN pip install --upgrade pip

# 2. [CRITICAL FIX] Force install the lightweight CPU-only version of PyTorch FIRST
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# 3. Install the rest of your requirements with a massively extended timeout
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# Download Spacy NLP model for Presidio (Required for PII detection)
RUN pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/en_core_web_lg-3.7.1-py3-none-any.whl
# ============================================================================
# STAGE 3: Application
# ============================================================================

FROM dependencies as application

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/v1/health')" || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
