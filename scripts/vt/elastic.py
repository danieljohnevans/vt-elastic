import os
from elasticsearch import Elasticsearch

def elastic_client():
    host = os.getenv('ES_HOST', 'https://es.viral-texts.software.ncsa.illinois.edu')
    user = os.getenv('ES_USER', 'elastic')
    password = os.getenv('ES_PASSWORD')
    client = Elasticsearch(
        hosts=host,
        basic_auth=(user, password),
        verify_certs=False,
        ssl_show_warn=False
    )

    return client
