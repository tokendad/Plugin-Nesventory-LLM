FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml /app/
COPY src/ /app/src/
COPY README.md /app/

# Install Python dependencies
# Note: In some environments with SSL proxy issues, you may need to set:
# ENV PIP_TRUSTED_HOST=pypi.org,files.pythonhosted.org
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .

# Create data and cache directories
RUN mkdir -p /app/data /app/.cache

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose API port
EXPOSE 8002

# Set default environment variables
ENV PUID=1000 \
    PGID=1000 \
    TZ=UTC

# Use entrypoint script
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command: start the API server
CMD ["serve"]
