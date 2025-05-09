import re
from flask import Flask, render_template, request, Response, redirect, url_for, jsonify
from search import Search
import csv
import io
from jinja2 import Undefined
from pprint import pprint
from datetime import datetime



app = Flask(__name__)
es = Search()

class CustomUndefined(Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):
        return redirect(url_for('index'))

app.jinja_env.undefined = CustomUndefined

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

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
        "size": 50
    }
    results = es.search(body=query)
    processed_data = []

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

@app.route('/', methods=['GET', 'POST'])

def handle_search():
    if request.method == 'GET' and 'query' not in request.args:
        return render_template('index.html', query='', raw_args={})
    
    data = request.args if request.method == 'GET' else request.form

    query   = data.get('query', '')
    from_   = data.get('from_', type=int) or 0
    sort_by = data.get('sort_by', 'count')

    filters, parsed_query = extract_filters(query)

    search_query = {
    "bool": {
        "must": [],
        "filter": []
    }
}

    if parsed_query:
        search_query['bool']['must'].append({
            "query_string": {
                "query": parsed_query if parsed_query else "*",
                "default_field": "text",  
                "default_operator": "AND",  
                "analyze_wildcard": True,
                
            }
        })
    else:
        search_query['bool']['must'].append({"match_all": {}})

    
    if 'location' in filters:
        search_query['bool']['filter'].append({
        "term": {
            "topdiv.keyword": filters['location']
        }
    })
        
    if 'cluster' in filters:
        year = filters['cluster']
        search_query['bool']['filter'].append({
            "term": {
            "cluster": filters['cluster']
        }
        })

    if 'year' in filters:
        year = filters['year']
        search_query['bool']['filter'].append({
            "range": {
                "date": {
                    "gte": f"{year}-01-01",
                    "lte": f"{year}-12-31"
                }
            }
        })

    results = es.search(
        body={
            "query": search_query,
            'aggs': {
                'category-agg': {
                    'terms': {
                        'field': 'topdiv.keyword',
                        # 'order': { "_count": "desc" }
                    }
                },
                'year-agg': {
                    'date_histogram': {
                        'field': 'date',
                        'calendar_interval': 'year',
                        'format': 'yyyy',
                        # 'order': { "_count": "desc" } 
                    }
                },
                'cluster-agg': {
                    'terms': {
                        'field': 'cluster',
                        
                        'size': 100, 
                        'include': {  
                            'partition': from_ // 50, 
                            'num_partitions': 10 
                        }
                    }
                },
                'cluster-count': {
                    'terms': {
                        'field': 'cluster',
                        "order": { "_count": "desc" },
                        'size': 10000
                    }
                },
                'total-clusters': {
                    'cardinality': {
                        'field': 'cluster.keyword'
                    }
                }
            },
            'size': 8700, 
            'from': from_, 
            'highlight': {
                'fields': {
                    'text': {
                        "pre_tags": ["<b>"], "post_tags": ["</b>"],
                        'fragment_size': 250
                    }
                }
            },
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
    }
    }

    cluster_aggregation = { 'Cluster': {
        bucket['key']: {'doc_count': bucket['doc_count']}
        for bucket in results['aggregations']['cluster-count']['buckets']
    },}

    sorted_cluster = sorted(cluster_aggregation['Cluster'].items(), key=lambda x: x[1]['doc_count'], reverse=True)

    clusters_data = results['aggregations']['cluster-agg']['buckets']
    clusters_data = clusters_data[from_:from_ + 50]

    # print(aggs)

    clusters_results = {}
    for hit in results['hits']['hits']:
        cluster = hit['_source'].get('cluster', None)
        if cluster and cluster in cluster_aggregation['Cluster']:
            source = hit['_source'].get('source', None)
            date = hit['_source'].get('date', None)
            open = hit['_source'].get('open', None)
            doc_count = hit['_source'].get('size', None)
            city = hit['_source'].get('city', None)
            date_range = hit['_source'].get('dateRange', None)
            if 'highlight' in hit:
                highlight = hit['highlight']
            else:
                highlight = {}

            if date_range:
                try:
                    min_year, max_year = map(int, date_range.split('/')) 
                except ValueError:
                    min_year, max_year = None, None 
            else:
                min_year, max_year = None, None  


            if cluster not in clusters_results:
                clusters_results[cluster] = []

            clusters_results[cluster].append({
                'source': source,
                'highlight': highlight,
                'date': date,
                'count': cluster_aggregation['Cluster'][cluster]['doc_count'],
                'open': open,
                'doc_count': doc_count,
                'date_range': date_range,
                'min_year': min_year,
                'max_year': max_year,
                'city': city

            })

    #sort based on cluster count
    clusters_results = dict(
        sorted(clusters_results.items(), key=lambda item: item[1][0]['count'], reverse=True)
    )

    # print(clusters_results)

    sorted_clusters_list = sorted(cluster_aggregation['Cluster'].items(), key=lambda item: item[1]['doc_count'], reverse=True)

    # print(sorted_clusters_list)

    # Sort clusters w info by count in descending order
    sorted_clusters_list = sorted(clusters_results.items(), key=lambda item: item[1][0]['count'], reverse=True)
    # print(sorted_clusters_list)

    if sort_by == "min_year":
        sorted_clusters_list = sorted(
            clusters_results.items(), 
            key=lambda item: item[1][0]['min_year'] if item[1][0]['min_year'] is not None else float('inf')
        )   
    elif sort_by == "max_year":
            sorted_clusters_list = sorted(
                clusters_results.items(), 
                key=lambda item: item[1][0]['max_year'] if item[1][0]['max_year'] is not None else float('inf')
            )    
    elif sort_by == "desc_count":
        sorted_clusters_list = sorted(sorted_clusters_list, key=lambda item: item[1][0]['count'], reverse=True)
    elif sort_by == "asc_count":
        sorted_clusters_list = sorted(sorted_clusters_list, key=lambda item: item[1][0]['count'], reverse=False)
    elif sort_by == "desc_cluster":
        sorted_clusters_list = sorted(sorted_clusters_list, key=lambda item: item[1][0]['doc_count'], reverse=True)
    elif sort_by == "asc_cluster":
        sorted_clusters_list = sorted(sorted_clusters_list, key=lambda item: item[1][0]['doc_count'], reverse=False)

    # Apply slicing for pagination
    clusters_results = dict(sorted_clusters_list[from_:from_ + 20])
    
    # print("Unique clusters returned:", len(clusters_results))
    # print(paginated_clusters)

    clusters = {
        'Cluster': {
            bucket['key']: {
                'doc_count': bucket['doc_count']
            }
            for bucket in results['aggregations']['cluster-agg']['buckets']
        },
    }


        ##### get min_date and max_date
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



    total_doc_count = sum(bucket['doc_count'] for bucket in clusters['Cluster'].values())

    return render_template('index.html', 
                        results=results['hits']['hits'],
                        query=query,
                        from_=from_,
                        total=results['hits']['total']['value'],
                        aggs=aggs,
                        clusters=clusters,
                        clusters_results=clusters_results,
                        cluster_aggregation=cluster_aggregation,
                        sorted_cluster=sorted_cluster,
                        # cluster_totals=cluster_totals,
                        # processed_clusters=processed_clusters, 
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
        searching_by_cluster = es.search(query=search_query, size=size, sort=[
        {"date": "asc"},
        {"ref": "desc"}
    ])
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

    
def extract_filters(query):
    filters = {}

    location_match = re.search(r"location:'([^']*)'", query)
    if location_match:
        filters['location'] = location_match.group(1)

    year_match = re.search(r"year:(\d{4})", query)
    if year_match:
        filters['year'] = int(year_match.group(1))
    
    
    cluster_match = re.search(r"cluster:'(\d+)'", query)
    if cluster_match:
        filters['cluster'] = int(cluster_match.group(1))

    parsed_query = query
    if 'location' in filters:
        parsed_query = re.sub(r"location:'[^']*'", '', parsed_query)
    if 'year' in filters:
        parsed_query = re.sub(r"\s*year:\d{4}\s*", ' ', parsed_query)
    if 'cluster' in filters:
        parsed_query = re.sub(r"'cluster:'(\d+)", ' ', parsed_query)

    parsed_query = parsed_query.strip()
    parsed_query = re.sub(r'\s+(AND|OR)\s+$', '', parsed_query)

    return filters, parsed_query
        
    

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    # app.run(debug=True)
    app.run()