#!/bin/sh
export ES_PASSWORD=${ES_PASSWORD}
export ES_USER=${ES_USER}
exec gunicorn --config gunicorn_config.py app:app