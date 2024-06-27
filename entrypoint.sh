#!/bin/sh

# Run Flask reindex command
flask reindex

# Start Gunicorn
exec gunicorn --config gunicorn_config.py app:app