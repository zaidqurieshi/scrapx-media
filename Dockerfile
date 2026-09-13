FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY config/ config/
COPY core/ core/
COPY database/ database/
COPY filters/ filters/
COPY scripts/ scripts/
COPY main.py .

# Create volume directories for session and database persistence
RUN mkdir -p data logs

VOLUME ["/app/data", "/app/logs"]

# Run the monitoring automation
CMD ["python", "main.py"]

