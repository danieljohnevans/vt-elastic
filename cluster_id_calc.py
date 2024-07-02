# this code is for debugging and constructing scrolling queries to help create pre-computed lists of clusters

from elasticsearch import Elasticsearch
import csv
import os
import time

es_host = os.getenv('ES_HOST', 'https://es.viral-texts.software.ncsa.illinois.edu')
es_user = os.getenv('ES_USER')
es_password = os.getenv('ES_PASSWORD')

     
        
es = Elasticsearch(
            es_host,
            basic_auth=(es_user, es_password)
        )

client_info = es.info()

print('Connected to Elasticsearch!')
print(client_info.body)


search_term = "test"

es_query = {
    "query": {
        "bool": {
            "must": 
                {"match_phrase": {"text": search_term}}
        }
    },
    "size": 5000  
}

scroll_time = '5m' 
scroll_id = None
total_hits = 0
processed_hits = 0


# Execute the initial Elasticsearch search
results = es.search(index="viral-texts-test", body=es_query, scroll=scroll_time)
total_hits = results['hits']['total']['value']
print(total_hits)
scroll_id = results['_scroll_id']
hits = results['hits']['hits']

cluster = []
while processed_hits < total_hits:
    scroll_response = es.scroll(scroll_id=scroll_id, scroll=scroll_time)
    hits = scroll_response['hits']['hits']
    if not hits:
        break
    for hit in hits:
        source = hit['_source']['cluster']
        print(source)  # Print or process each document as needed
        cluster.append(hit['_source']['cluster'])
        processed_hits += 1

    scroll_id = scroll_response['_scroll_id']

    # Example: Pause for a moment to avoid overloading Elasticsearch
    time.sleep(3)

csv_file = 'my_list.csv'

# Write the list to a CSV file
with open(csv_file, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['items'])  # Write header
    for item in cluster:
        writer.writerow([item])