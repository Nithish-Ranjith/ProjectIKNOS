FROM python:3.10-slim

# Install system GIS and OpenCV dependencies
RUN apt-get update && apt-get install -y \
    gdal-bin libgdal-dev g++ \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set up GDAL env vars
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/

# Note: The ML models should be mounted into /app/models or copied here if deploying directly.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
