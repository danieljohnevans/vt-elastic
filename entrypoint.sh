#!/bin/sh

# flask reindex

exec gunicorn --config gunicorn_config.py app:app