import sys
import os
from app import app  # Import your Flask or WSGI app

username = os.getenv("ES_USERNAME")
password = os.getenv("ES_PASSWORD")

if not username or not password:
    raise RuntimeError("Elasticsearch credentials (ES_USERNAME, ES_PASSWORD) are not set in the environment variables.")

path = '/var/www/webroot/ROOT'
if path not in sys.path:
    sys.path.append(path)

application = app