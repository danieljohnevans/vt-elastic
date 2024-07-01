import json
from pprint import pprint

from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import os

load_dotenv()


class Search:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        # self.es = Elasticsearch('http://elastic-vt:9200') # < --- use for local docker 

        # self.es = Elasticsearch('http://localhost:9200')  # <-- connection options need to be added here
        es_host = os.getenv('ES_HOST', 'https://es.viral-texts.software.ncsa.illinois.edu')
        es_user = os.getenv('ES_USER')
        es_password = os.getenv('ES_PASSWORD')

        self.es = Elasticsearch(
            es_host,
            http_auth=(es_user, es_password)
        )

        client_info = self.es.info()
        print('Connected to Elasticsearch!')
        pprint(client_info.body)
    
    # def create_index(self):
    #     self.es.indices.delete(index='search', ignore_unavailable=True)
    #     self.es.indices.create(index='search', mappings={
    #         'properties': {
    #             'embedding': {
    #                 'type': 'dense_vector',
    #             }
    #         }
    #     })
    
    def get_embedding(self, text):
        return self.model.encode(text)


    # def insert_documents(self, documents):
    #     operations = []
    #     for document in documents:
    #         operations.append({'index': {'_index': 'search'}})
    #         operations.append(document)
    #     return self.es.bulk(operations=operations)

# this is for embedding search
    # def insert_documents(self, documents):
    #     operations = []
    #     for document in documents:
    #         operations.append({'index': {'_index': 'search'}})
    #         operations.append({
    #             **document,
    #             'embedding': self.get_embedding(document['text']),
    #         })
    #     return self.es.bulk(operations=operations)

    # def insert_documents(self, documents, chunk_size=100):
    #     total_documents = len(documents)
    #     for i in range(0, total_documents, chunk_size):
    #         chunk = documents[i:i+chunk_size]
    #         operations = []
    #         for document in chunk:
    #             if 'text' in document:
    #                 operations.append({'index': {'_index': 'search'}})
    #                 operations.append({
    #                     'text': document['text'],
    #                     'embedding': self.get_embedding(document['text']),
    #                     **{k: v for k, v in document.items() if k != 'text'}
    #                 })
    #             else:
    #                 print("Warning: 'text' field not found in document.")
    #         response = self.es.bulk(operations=operations)
    #     return response
    
    #turning off reindexing
    # def reindex(self):
    #     self.create_index()
    #     with open('assets/combined_output.json', 'rt') as f:
    #         documents = json.loads(f.read())

        # only inserts open  documents
        # filtered_documents = [doc for doc in documents if doc.get("open") == 'true']
               
        # return self.insert_documents(filtered_documents)

        # return self.insert_documents(documents)

    
    def search(self,  **query_args,):
        return self.es.search(index='viral-texts-test', **query_args)
    
    def retrieve_document(self, id):
        return self.es.get(index='viral-texts-test', id=id)
    
    def retrieve_cluster(self, cluster_value, search_term):

        query = {
            "query": {
                "match": {
                    "cluster": cluster_value
                }
            },
            "highlight": {
                "fields": {
                    'text': { "pre_tags" : ["<b>"], "post_tags" : ["</b>"]}
                }
            }
        }
        

        # run query twice. first is to get size of hit_count then again w dynamically updated size
        
        result = self.es.search(index='viral-texts-test', body=query)
        hits_count = result['hits']['total']['value']
        size = hits_count
        result = self.es.search(index='viral-texts-test', body=query, size=size)

        #only returns first item else returns none
        if result['hits']['total']['value'] > 0:
            return [hit['_source'] for hit in result['hits']['hits']]
        else:
            return None
        
    def scroll(self, scroll_id, scroll):
        return self.es.scroll(scroll_id=scroll_id, scroll=scroll)

    def clear_scroll(self, scroll_id):
        self.es.clear_scroll(scroll_id=scroll_id)