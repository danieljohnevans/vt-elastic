import json
from pprint import pprint
import os
import time
import gzip


from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()


class Search:
    def __init__(self):
        self.es = Elasticsearch('http://localhost:9200')  # <-- connection options need to be added here
        client_info = self.es.info()
        print('Connected to Elasticsearch!')
        pprint(client_info.body)
    
    def create_index(self):
        self.es.indices.delete(index='search', ignore_unavailable=True)
        self.es.indices.create(index='search')

    def insert_documents(self, documents):
        operations = []
        for document in documents:
            operations.append({'index': {'_index': 'search'}})
            operations.append(document)
        return self.es.bulk(operations=operations)
    
    def reindex(self):
        self.create_index()
        with open('assets/combined_output.json', 'rt') as f:
            documents = json.loads(f.read())

        # only inserts open  documents
        # filtered_documents = [doc for doc in documents if doc.get("open") == 'true']
               
        # return self.insert_documents(filtered_documents)

        return self.insert_documents(documents)

    
    def search(self, **query_args):
        return self.es.search(index='search', **query_args)
    
    def retrieve_document(self, id):
        return self.es.get(index='search', id=id)
    
    def retrieve_cluster(self, cluster_value):

        #create query
        query = {
            "query": {
                "match": {
                    "cluster": cluster_value
                }
            },
            "sort": [
                {"_score": {"order": "desc"}},
                {
                    "text.keyword": {
                        "order": "asc"
                    }
                }
            ]
        }

        # run query twice. first is to get size of hit_count then again w dynamically updated size
        result = self.es.search(index='search', body=query)
        hits_count = result['hits']['total']['value']
        size = hits_count
        result = self.es.search(index='search', body=query, size=size)

        #only returns first item else returns none
        if result['hits']['total']['value'] > 0:
            return [hit['_source'] for hit in result['hits']['hits']]
        else:
            return None