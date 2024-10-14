import sys
import os
import stat

APP_PATH = '/var/www/webroot/ROOT'

if APP_PATH not in sys.path:
    sys.path.append(APP_PATH)

def set_permissions(path):
    """Set the ownership and permissions for the given path."""
    # os.system(f"sudo chown -R www-data:www-data {path}")

    os.system(f"find {path} -type d -exec chmod 755 {{}} \\;")

    os.system(f"find {path} -type f -exec chmod 644 {{}} \\;")

    os.system(f"chmod 644 {path}/.env")

set_permissions(APP_PATH)

from dotenv import load_dotenv
load_dotenv()

es_user = os.getenv("ES_USER")
es_password = os.getenv("ES_PASSWORD")

if not es_user or not es_password:
    raise RuntimeError("Elasticsearch credentials (ES_USER, ES_PASSWORD) are not set in the environment variables.")

from app import app
application = app
