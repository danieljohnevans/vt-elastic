import os
from elasticsearch import Elasticsearch

def elastic_client ():
    url = os.environ.get("ELASTIC_URL")
    password = os.environ.get("ELASTIC_PASSWORD")
    client = Elasticsearch(
        hosts=url,
        basic_auth=("elastic", password)
    )

    return client
