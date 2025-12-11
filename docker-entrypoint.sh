#!/bin/bash
set -e

# Set up user/group based on PUID/PGID
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Set timezone
if [ -n "$TZ" ]; then
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime
    echo $TZ > /etc/timezone
fi

# Create group if it doesn't exist
if ! getent group $PGID > /dev/null 2>&1; then
    groupadd -g $PGID nesventory
fi

# Create user if it doesn't exist
if ! getent passwd $PUID > /dev/null 2>&1; then
    useradd -u $PUID -g $PGID -d /app -s /bin/bash nesventory
fi

# Fix permissions for data and cache directories
chown -R $PUID:$PGID /app/data /app/.cache

# Create cache subdirectories for ML models
mkdir -p /app/.cache/huggingface /app/.cache/torch /app/.cache/Ultralytics/weights
chown -R $PUID:$PGID /app/.cache

# Initialize sample data if data directory is empty
if ! find /app/data -name '*.json' -type f | grep -q .; then
    echo "Initializing sample data..."
    gosu $PUID:$PGID python -c "from plugin_nesventory_llm.seed_data import save_sample_data; save_sample_data()" || echo "Warning: Could not generate sample data"
fi

# Execute command as the specified user
if [ "$1" = "serve" ]; then
    exec gosu $PUID:$PGID nesventory-llm serve --host 0.0.0.0 --port 8002
else
    exec gosu $PUID:$PGID "$@"
fi
