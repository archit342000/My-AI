FROM python:3.12-slim

# Create a non-root user and group with explicit UID/GID matching the host
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appuser && useradd -m -u ${UID} -g appuser appuser

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create the data directory and set permissions
# This ensures appuser has explicit rights, even though volumes might overwrite
RUN mkdir -p /app/backend/data && chown -R appuser:appuser /app

# Copy application files with appropriate ownership
COPY --chown=appuser:appuser . .

# Run as non-root user
USER appuser

# Set unbuffered python output
ENV PYTHONUNBUFFERED=1

# Expose the Flask port
EXPOSE 5000

# Start application
CMD ["python3", "app.py"]
