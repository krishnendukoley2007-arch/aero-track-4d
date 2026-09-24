# AERO-TRACK 4D // Production Container Image
FROM python:3.11-slim

# Prevent Python from writing .pyc and buffer stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU-only first for smaller image footprint (~350MB vs ~3GB GPU)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY dashboard/ ./dashboard/
COPY data/ ./data/
COPY models/ ./models/
COPY src/ ./src/
COPY test_smoke.py .

# Run smoke test during build to verify integrity
RUN python test_smoke.py

EXPOSE 8000

# Start server binding to all interfaces and respecting $PORT for cloud hosts (Render/Railway/CloudRun)
CMD ["sh", "-c", "python -m uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
