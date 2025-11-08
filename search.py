from pprint import pprint

from dotenv import load_dotenv
from elasticsearch import Elasticsearch
import os
import urllib.parse


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
    
    def get_cluster_count(self, cluster_id: int) -> int:
        """
        Return the number of documents belonging to a given cluster.
        """
        body = {
            "query": {"term": {"cluster": cluster_id}},
            "size": 0  # we only need the count
        }
        resp = self.search(body=body)
        return resp["hits"]["total"]["value"]
        
    
    def get_boxes_for_manifest_page(self, manifest_id: str, seq: int | None = None, size: int = 5000):
        """
        Return all bounding boxes for records whose p1iiif contains the given manifest_id.
        If seq is provided, restrict to that page (p1seq).
        """
        must = [
            {
                "bool": {
                    "should": [
                        {"wildcard": {"p1iiif.keyword": f"*{manifest_id}*"}},
                        {"wildcard": {"url.keyword":   f"*{manifest_id}*"}},
                    ],
                    "minimum_should_match": 1
                }
            }
        ]
        if seq is not None:
            must.append({"term": {"p1seq": seq}})

        body = {
            "query": {"bool": {"must": must}},
            "_source": ["id", "p1seq", "p1x", "p1y", "p1w", "p1h", "p1width", "p1height", "cluster", "source"],
            "size": size,
            "sort": [
                {"date": "asc"},
                {"ref": "desc"}
            ]
        }
        resp = self.search(body=body)
        out = []
        for hit in resp["hits"]["hits"]:
            s = hit["_source"]
            out.append({
                "manifest_id": s.get("id"),
                "seq":        int(s.get("p1seq") or 0),
                "cluster":    s.get("cluster"),
                "label":      s.get("source") or f"Cluster {s.get('cluster')}",
                "x":          s.get("p1x"),
                "y":          s.get("p1y"),
                "w":          s.get("p1w"),
                "h":          s.get("p1h"),
                "img_w":      s.get("p1width"),
                "img_h":      s.get("p1height"),
            })
        return out


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