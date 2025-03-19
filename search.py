from pprint import pprint

from dotenv import load_dotenv
from elasticsearch import Elasticsearch
import os
from datetime import datetime

load_dotenv()


class Search:
    def __init__(self):
        es_host = os.getenv('ES_HOST', 'https://es.viral-texts.software.ncsa.illinois.edu')
        es_user = os.getenv('ES_USER')
        es_password = os.getenv('ES_PASSWORD')

        self.es = Elasticsearch(
            es_host,
            basic_auth=(es_user, es_password)
        )

        client_info = self.es.info()
        print('Connected to Elasticsearch!')
        pprint(client_info.body)

    
    def search(self,  **query_args,):
        return self.es.search(index='viral-texts', **query_args)
    
    def retrieve_document(self, id):
        return self.es.get(index='viral-texts', id=id)

    

    #no longer necessary. pulling data size data from metadata and reprints from aggs 2/25. keep in for a few cycles
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
            },
            "sort": [
            {"date": "asc"}, 
            {"ref": "desc"}   
        ]
        }
        

    #     # run query twice. first is to get size of hit_count then again w dynamically updated size
        
        result = self.es.search(index='viral-texts', body=query)
        hits_count = result['hits']['total']['value']
        size = hits_count
        result = self.es.search(index='viral-texts', body=query, size=size)

        #only returns first item else returns none
        if result['hits']['total']['value'] > 0:
            return [hit['_source'] for hit in result['hits']['hits']]
        else:
            return None
        
    def scroll(self, scroll_id, scroll):
        return self.es.scroll(scroll_id=scroll_id, scroll=scroll)

    def clear_scroll(self, scroll_id):
        self.es.clear_scroll(scroll_id=scroll_id)