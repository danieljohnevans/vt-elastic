import re
from flask import Flask, render_template, request, Response, redirect, url_for, jsonify
from search import Search
import csv
import io
from jinja2 import Undefined
from pprint import pprint




app = Flask(__name__)
es = Search()

class CustomUndefined(Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):
        return redirect(url_for('index'))

app.jinja_env.undefined = CustomUndefined


@app.get('/')
def index():
    return render_template('index.html')


# this is for embedding search

# @app.post('/')
# def handle_search():
#     query = request.form.get('query', '')
#     filters, parsed_query = extract_filters(query)
#     from_ = request.form.get('from_', type=int, default=0)

#     results = es.search(
#         knn={
#             'field': 'embedding',
#             'query_vector': es.get_embedding(parsed_query),
#             'num_candidates': 50,
#             'k': 10,
#         },
#         size=5,
#         from_=from_
#     )
#     return render_template('index.html', results=results['hits']['hits'],
#                            query=query, from_=from_,
#                            total=results['hits']['total']['value'])


def process_clusters_results(clusters, search_phrase):

    cluster_keys = [str(key) for key in clusters['Cluster'].keys()]


# can adjust size here
    query = {
        "query": {
            "bool": {
                "must": [
                    {"terms": {"cluster": cluster_keys}},
                    {"match_phrase": {"text": search_phrase}}
                ]
            }
        },
        "highlight": {
            "fields": {
                'text': {
                    "pre_tags": ["<b>"],
                    "post_tags": ["</b>"],
                    "fragment_size": 250
                }
            }
        },
        "size": 10
    }
    results = es.search(body=query)
    processed_data = []

    # for cluster_name, cluster_data in clusters.items():
    #     for key, data in cluster_data.items():
    #         doc_count = data['doc_count']
    #         result_found = False
    #         result_details = {}

    for hit in results['hits']['hits']:
        open = hit['_source']['open']
        cluster = hit['_source']['cluster']
        source = hit['_source'].get('source', None)
        date = hit['_source']['date']
        text = hit['_source']['text']
        highlight = hit['highlight']['text'][0]
        
        processed_data.append({
            'open': open,
            'cluster': cluster,
            'source': source,
            'date': date,
            'text': text,
            'highlight': highlight
        })


    return processed_data

@app.post('/')
def handle_search():
    query = request.form.get('query', '')
    filters, parsed_query = extract_filters(query)
    from_ = request.form.get('from_', type=int, default=0)

    if parsed_query:
        search_query = {
            "query_string": {
                "query": parsed_query,
                "default_field": "text",  
                "default_operator": "AND",  
                "analyze_wildcard": True, 
            }
        }
    else:
        search_query = {
            "match_all": {}
        }

    
    #use the to update size, resizing not currently working correctly
        # result = es.search(query={
        #     'bool': {
        #         **search_query,
        #         **filters,
        #     },          
        # })

    results = es.search(
        body={
            "query": search_query,
           'aggs': {
                'category-agg': {
                    'terms': {
                        'field': 'topdiv.keyword',
                    }
                },
                'year-agg': {
                    'date_histogram': {
                        'field': 'date',
                        'calendar_interval': 'year',
                        'format': 'yyyy',
                    }
                },
                'cluster-agg': {
                    'terms': {
                        'field': 'cluster',
                        'size': 50, 
                        'include': {  
                            'partition': from_ // 50, 
                            'num_partitions': 10 
                        }
                    }
                },
                'cluster-count': {
                    'terms': {
                        'field': 'cluster',
                        'size': 10000
                    }
                },
                'total-clusters': {
                    'cardinality': {
                        'field': 'cluster.keyword'
                    }
                }
            },
            'size': 50,  
            'from': from_,  
            'highlight': {
                'fields': {
                    'text': {
                        "pre_tags": ["<b>"], "post_tags": ["</b>"],
                        'fragment_size': 250
                    }
                }
            }
        }
    )




    aggs = {
    'Location': {
        bucket['key']: bucket['doc_count']
        for bucket in sorted(results['aggregations']['category-agg']['buckets'], key=lambda x: x['key'])
    }, 
    'Year': {
        bucket['key_as_string']: bucket['doc_count']
        for bucket in results['aggregations']['year-agg']['buckets']
        if bucket['doc_count'] > 0
    },
    # 'Cluster': {
    #     bucket['key']: bucket['doc_count']
    #     for bucket in results['aggregations']['cluster-agg']['buckets']
    # },
    }

    cluster_aggregation = { 'Cluster': {
        bucket['key']: {'doc_count': bucket['doc_count']}
        for bucket in results['aggregations']['cluster-count']['buckets']
    },}

    clusters_results = {}
    for hit in results['hits']['hits']:
        cluster = hit['_source'].get('cluster', None)
        if cluster and cluster in cluster_aggregation['Cluster']:
            # print(f"Cluster: {cluster}, Count: {cluster_aggregation['Cluster'][cluster]['doc_count']}")
            source = hit['_source'].get('source', None)
            highlight = hit['highlight']
            date = hit['_source'].get('date', None)

            if cluster not in clusters_results:
                clusters_results[cluster] = []

            clusters_results[cluster].append({
                'source': source,
                'highlight': highlight,
                'date': date,
                'count': cluster_aggregation['Cluster'][cluster]['doc_count']
            })




    clusters_data = results['aggregations']['cluster-agg']['buckets']

    clusters = {
        'Cluster': {
            bucket['key']: {
                'doc_count': bucket['doc_count']
            }
            for bucket in clusters_data
        },
    }

    total_doc_count = sum(bucket['doc_count'] for bucket in clusters['Cluster'].values())

    search_phrase = query

    processed_clusters = process_clusters_results(clusters, search_phrase)

    cluster_date_info = {}
    for key in clusters_results:
        clustr = es.retrieve_cluster(key, query)
        dates = [document.get('date', '') for document in clustr]



        if dates:
            min_date = min(dates)
            max_date = max(dates)
        else:
            min_date = None
            max_date = None

        cluster_date_info[key] = {'min_date': min_date, 'max_date': max_date}
    

    for key in clusters_results:
        cluster_data = clusters_results[key]
        date_info = cluster_date_info[key]

        for entry in cluster_data:
            entry['min_date'] = date_info['min_date']
            entry['max_date'] = date_info['max_date']

    cluster_totals = {key: len(es.retrieve_cluster(key, query)) for key in clusters_results}


    # print(len(cluster_aggregation['Cluster']))
    

    return render_template('index.html', 
                        results=results['hits']['hits'],
                        query=query,
                        from_=from_,
                        total=results['hits']['total']['value'],
                        aggs=aggs,
                        clusters=clusters,
                        clusters_results=clusters_results,
                        cluster_aggregation=cluster_aggregation,
                        cluster_totals=cluster_totals,
                        processed_clusters=processed_clusters, 
                        total_doc_count=total_doc_count)

@app.get('/document/<id>')
def get_document(id):

    document = es.retrieve_document(id)
    search_term = request.args.get('search_term', '')

    corpus = document['_source']['corpus']


    if '_source' in document and 'page_image' in document['_source']:
        images = document['_source']['page_image']
    else:
        images = None

    if '_source' in document and 'url' in document['_source']:
        url = document['_source']['url']
    else:
        url = None
    
    
    if '_source' in document and 'coverage' in document['_source']:
        coverage = document['_source']['coverage']
    else:
        coverage = None

    if '_source' in document and 'p1seq' in document['_source']:
        canvas_index=document['_source']['p1seq']
    else:
        canvas_index = None

    if '_source' in document and 'series' in document['_source']:
        series=document['_source']['series']
    else:
        group = None

    if '_source' in document and 'ed' in document['_source']:
        ed=document['_source']['ed']
    else:
        ed = None
    
    if '_source' in document and 'pp' in document['_source']:
        pp=document['_source']['pp']
    else:
        pp = None

            


    # to convert chron am image urls
    if corpus == 'ca':
        ca_images = images
    else:
        ca_images = ''

    regex = re.compile(r"https://chroniclingamerica\.loc\.gov/iiif/2/(service%2F[\w%2F]+)\.jp2(/pct:[\d.,]+/full/0/default\.jpg)")

    match = regex.match(ca_images)
    if match:
        identifier = match.group(1)
        region_and_more = match.group(2)
        identifier_parts = identifier.split('%2F')
        new_identifier = ':'.join(identifier_parts) + region_and_more

        base_url = "https://tile.loc.gov/image-services/iiif/"
        ca_images = f"{base_url}{new_identifier}"

        # print(ca_images)
    else:
        # print("The URL format is not recognized.")
        ca_images = None


    title = document['_source']['source']
    paragraphs = document['_source']['text'].split('\n')
    # place = document['_source']['placeOfPublication']
    date = document['_source']['date']
    open=document['_source']['open']
    manifest_id=document['_source']['id']

    return render_template('document.html', title=title, paragraphs=paragraphs, images=images, url=url, coverage=coverage, date=date, open=open, search_term=search_term, corpus=corpus,manifest_id=manifest_id,canvas_index=canvas_index, ca_image=ca_images,series=series,ed=ed,pp=pp)

@app.get('/cluster/<cluster_id>')
def get_cluster(cluster_id):


    search_term = request.args.get('search_term', '')
    cluster = es.retrieve_cluster(cluster_id, search_term)

    if search_term.startswith('"') and search_term.endswith('"'):
        search_term = search_term[1:-1]

    if cluster:

        images = [document.get('page_image', '') for document in cluster]
        coverage = [document.get('coverage', '') for document in cluster]
        url = [document.get('url', '') for document in cluster]
        titles = [document.get('source', '') for document in cluster]
        # paragraphs = document['_source']['text'].split('\n')
        paragraphs = [document.get('text', '').split('\n') for document in cluster]
        csv_paragraphs = [document.get('text', '') for document in cluster]
        place = [document.get('placeOfPublication', '') for document in cluster]
        ia_place = [document.get('placeOfPublication', '') for document in cluster]

        date = [document.get('date', '') for document in cluster]
        open= [document.get('open', '') for document in cluster]
        corpus = [document.get('corpus', '') for document in cluster]
        cluster= [document.get('cluster', '') for document in cluster]


        search_query = {"match": {"cluster": cluster[-1]}}
        first = es.search(query=search_query)
        hits_count = first['hits']['total']['value']
        size = hits_count
        searching_by_cluster = es.search(query=search_query, size=size)
        searching_by_cluster = searching_by_cluster['hits']
        uid = [hit['_id'] for hit in searching_by_cluster['hits']]

        ca_images = []
            # to convert chron am image urls
        for item in corpus:
            if item == 'ca':
                ca_image = images

                regex = re.compile(r"https://chroniclingamerica\.loc\.gov/iiif/2/(service%2F[\w%2F]+)\.jp2(/pct:[\d.,]+/full/0/default\.jpg)")
                for i in ca_image:
                    match = regex.match(i)
                    if match:
                        identifier = match.group(1)
                        region_and_more = match.group(2)
                        identifier_parts = identifier.split('%2F')
                        new_identifier = ':'.join(identifier_parts) + region_and_more

                        base_url = "https://tile.loc.gov/image-services/iiif/"
                        ca_image = f"{base_url}{new_identifier}"
                        ca_images.append(ca_image)

                        # print(new_url)
                    else:
                        # print("The URL format is not recognized.")
                        pass



        filtered_data = [(title, csv_paragraphs, p, d, o, u, c, i, n, m)
                 if o.lower() == 'true' else (title, '', p, d, o, u, c, i, n, m)
                 for title, csv_paragraphs, p, d, o, u, c, i, n, m in zip(titles, csv_paragraphs, place, date, open, url, coverage, images, uid, cluster)]

        if request.args.get('download_csv'):
            csv_filename = f'cluster_{cluster_id}_data.csv'
            csv_data = filtered_data 

            response = Response(
                csv_generator(csv_data),
                content_type='text/csv',
                headers={'Content-Disposition': f'attachment; filename={csv_filename}'}
            )

            return response

        return render_template('cluster.html', titles=titles, paragraphs=paragraphs, place=place, date=date, open=open, url=url, coverage=coverage, images=images, search_term=search_term, cluster_id=cluster_id, uid=uid, ca_images=ca_images, corpus=corpus, ia_place=ia_place)

    return render_template('cluster.html', titles=[])

def csv_generator(data):
    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer)

    csv_writer.writerow(['Title', 'Paragraphs', 'Place', 'Date', 'Open', 'URL', 'Coverage', 'Images', 'Witness_id', 'Cluster_id'])

    for row in data:
        csv_writer.writerow(row)

    csv_buffer.seek(0)
    yield csv_buffer.read()


# @app.cli.command()
# def reindex():
#     """Regenerate the Elasticsearch index."""
#     response = es.reindex()
#     print(f'Index with {len(response["items"])} documents created '
#           f'in {response["took"]} milliseconds.')
    
def extract_filters(query):
    filters = []

    filter_regex = r"location:'([^']+)'"
    m = re.search(filter_regex, query)
    if m:
        filters.append({
            'term': {
                'topdiv.keyword': {
                    'value': m.group(1)
                }
            },
        })
        query = re.sub(filter_regex, '', query).strip()
        
    
    # filter_regex = r'cluster:([^\s]+)\s*'
    # m = re.search(filter_regex, query)
    # if m:
    #     filters.append({
    #         'term': {
    #             'cluster': {
    #                 'value': m.group(1)
    #             }
    #         },
    #     })
    #     query = re.sub(filter_regex, '', query).strip()

    filter_regex = r'year:([^\s]+)\s*'
    m = re.search(filter_regex, query)
    if m:
        filters.append({
            'range': {
                'date': {
                    'gte': f'{m.group(1)}||/y',
                    'lte': f'{m.group(1)}||/y',
                }
            },
        })
        query = re.sub(filter_regex, '', query).strip()

    return {'filter': filters}, query

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    # app.run(debug=True)
    app.run()