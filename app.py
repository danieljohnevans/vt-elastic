import re
from flask import Flask, render_template, request, Response
from search import Search
import csv
import io


app = Flask(__name__)
es = Search()



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


@app.post('/')
def handle_search():
    query = request.form.get('query', '')
    filters, parsed_query = extract_filters(query)
    from_ = request.form.get('from_', type=int, default=0)

    if parsed_query:
        search_query = {
            'must': {
                'multi_match': {
                    'query': parsed_query,
                    'fields': ['name', 'summary', 'text'],
                }
            }
        }
    else:
        search_query = {
            'must': {
                'match_all': {}
            }
        }

    results = es.search(
        query={
            'bool': {
                **search_query,
                **filters
            }
        },
        aggs={
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
                },
            },
    },
        size=10,
        from_=from_
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
    }

    return render_template('index.html', results=results['hits']['hits'],
                           query=query, from_=from_,
                           total=results['hits']['total']['value'],
                           aggs=aggs)


@app.get('/document/<id>')
def get_document(id):

    document = es.retrieve_document(id)
    search_term = request.args.get('search_term', '')

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

    title = document['_source']['source']
    paragraphs = document['_source']['text'].split('\n')
    place = document['_source']['placeOfPublication']
    date = document['_source']['date']
    open=document['_source']['open']
    return render_template('document.html', title=title, paragraphs=paragraphs, images=images, url=url, coverage=coverage, place=place, date=date, open=open, search_term=search_term)

@app.get('/cluster/<cluster_id>')
def get_cluster(cluster_id):


    cluster = es.retrieve_cluster(cluster_id)
    search_term = request.args.get('search_term', '')


    if cluster:

        images = [document.get('page_image', '') for document in cluster]
        coverage = [document.get('coverage', '') for document in cluster]
        url = [document.get('url', '') for document in cluster]
        titles = [document.get('source', '') for document in cluster]
        # paragraphs = document['_source']['text'].split('\n')
        paragraphs = [document.get('text', '').split('\n') for document in cluster]
        place = [document.get('placeOfPublication', '') for document in cluster]
        date = [document.get('date', '') for document in cluster]
        open= [document.get('open', '') for document in cluster]

        filtered_data = [(title, paragraph, p, d, o, u, c, i)
                                for title, paragraph, p, d, o, u, c, i in zip(titles, paragraphs, place, date, open, url, coverage, images)
                                if o.lower() == 'true']

        if request.args.get('download_csv'):
            csv_filename = f'cluster_{cluster_id}_data.csv'
            csv_data = filtered_data

            response = Response(
                csv_generator(csv_data),
                content_type='text/csv',
                headers={'Content-Disposition': f'attachment; filename={csv_filename}'}
            )

            return response

        return render_template('cluster.html', titles=titles, paragraphs=paragraphs, place=place, date=date, open=open, url=url, coverage=coverage, images=images, search_term=search_term, cluster_id=cluster_id)

    return render_template('cluster.html', titles=[])

def csv_generator(data):
    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer)

    # Write CSV header
    csv_writer.writerow(['Title', 'Paragraphs', 'Place', 'Date', 'Open', 'URL', 'Coverage', 'Images'])

    # Write data rows
    for row in data:
        csv_writer.writerow(row)

    csv_buffer.seek(0)
    yield csv_buffer.read()


@app.cli.command()
def reindex():
    """Regenerate the Elasticsearch index."""
    response = es.reindex()
    print(f'Index with {len(response["items"])} documents created '
          f'in {response["took"]} milliseconds.')
    
def extract_filters(query):
    filters = []

    filter_regex = r'location:([^\s]+)\s*'
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