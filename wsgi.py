
import sys

path = '/var/www/webroot/ROOT'
if path not in sys.path:
    sys.path.append(path)

import os
from dotenv import load_dotenv
from app import app  

load_dotenv()


es_user = os.getenv("ES_USER")
es_password = os.getenv("ES_PASSWORD")

if not es_user or not password:
    raise RuntimeError("Elasticsearch credentials (ES_USER, ES_PASSWORD) are not set in the environment variables.")


application = app