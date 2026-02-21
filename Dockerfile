FROM python:3.12-slim

# Install system dependencies including FFmpeg and pciutils (for nvidia-smi if passed through)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    pciutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy application requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY sizetrimmer.py db.py ./
COPY web/ ./web/

# Ensure data directory exists
RUN mkdir -p /app/data

# Expose the web UI port
EXPOSE 8000

# Set environment variables for storage
ENV DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python3", "sizetrimmer.py"]
