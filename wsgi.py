import sys
import os
from dotenv import load_dotenv

path = '/var/www/webroot/ROOT'
if path not in sys.path:
    sys.path.append(path)

    
from app import app  

load_dotenv()


username = os.getenv("ES_USER")
password = os.getenv("ES_PASSWORD")

if not username or not password:
    raise RuntimeError("Elasticsearch credentials (ES_USER, ES_PASSWORD) are not set in the environment variables.")


application = app