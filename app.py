import re, requests
from flask import Flask, render_template, request, Response, redirect, url_for, jsonify, make_response, abort

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


@app.get("/loc-proxy")
def loc_proxy():
    url = request.args.get("url")
    if not url or not url.startswith("https://www.loc.gov/"):
        abort(400, "Missing or invalid url")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    resp = make_response(r.content)
    resp.headers["Content-Type"] = r.headers.get("Content-Type", "application/json")
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.get('/document/<id>')
def get_document(id):

    document = es.retrieve_document(id)
    search_term = request.args.get('search_term', '')
    src = document['_source']

    corpus = src['corpus']


    if '_source' in document and 'page_image' in src:
        images = src['page_image']
    else:
        images = None

    if '_source' in document and 'url' in src:
        url = src['url']
    else:
        url = None
    
    
    if '_source' in document and 'coverage' in src:
        coverage = src['coverage']
    else:
        coverage = None

    if '_source' in document and 'p1seq' in src:
        canvas_index=src['p1seq']
    else:
        canvas_index = None

    if '_source' in document and 'series' in src:
        series=src['series']
    else:
        group = None

    if '_source' in document and 'ed' in src:
        ed=src['ed']
    else:
        ed = None
    
    if '_source' in document and 'pp' in src:
        pp=src['pp']
    else:
        pp = None


    loc_manifest_url = None

    if corpus.startswith(('ca', 'acdc')):  
        try:
            loc_manifest_url = loc_manifest_url_from_fields(
                src.get('series'),  # e.g. "/lccn/sn83030212"
                src.get('date'),    # e.g. "1842-01-06"
                src.get('ed')       # e.g. "1"
            )
        except Exception:
            loc_manifest_url = None
            


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

    return render_template('document.html', title=title, paragraphs=paragraphs, images=images, url=url, coverage=coverage, date=date, open=open, search_term=search_term, corpus=corpus,manifest_id=manifest_id,canvas_index=canvas_index, ca_image=ca_images,series=series,ed=ed,pp=pp,doc_id=id,      loc_manifest_url=loc_manifest_url)



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



def _parse_pct_from_page_image(url: str):
    m = re.search(r"/pct:([\d.]+),([\d.]+),([\d.]+),([\d.]+)/", url or "")
    if not m:
        return None
    return dict(x=float(m.group(1)), y=float(m.group(2)),
                w=float(m.group(3)), h=float(m.group(4)))



def _ia_canvas_id_from_manifest(manifest_id: str, seq: int):
    url = f"https://iiif.archive.org/iiif/3/{manifest_id}/manifest.json"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    items = data.get("items", [])
    if seq < 0 or seq >= len(items):
        raise IndexError(f"Canvas index {seq} out of range (0..{len(items)-1})")
    canvas = items[seq]
    return canvas["id"], canvas.get("width"), canvas.get("height")

def loc_manifest_url_from_fields(series: str, date_str: str, ed: str) -> str:
    """
    Convert ES fields to a LOC Presentation API 3 manifest URL.
    Example:
      series="/lccn/sn83030212", date="1842-01-06", ed="1"
      -> https://www.loc.gov/item/sn83030212/1842-01-06/ed-1/manifest.json
    """
    if not (series and date_str and ed):
        raise ValueError("Missing one of series/date/ed for LOC manifest")

    # extract "sn83030212" from "/lccn/sn83030212"
    parts = series.strip("/").split("/")
    if len(parts) < 2 or parts[0] != "lccn":
        raise ValueError(f"Unexpected series format: {series}")
    lccn = parts[1]

    return f"https://www.loc.gov/item/{lccn}/{date_str}/ed-{ed}/manifest.json"


def _loc_canvas_id_with_dims(series: str, date_str: str, ed: str, seq: int):
    """
    Retrieve a canvas ID and dimensions from a LOC IIIF manifest.
    Supports both IIIF Presentation v2 (sequences/canvases)
    and v3 (items).
    """
    url = loc_manifest_url_from_fields(series, date_str, ed)
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()

    items = data.get("items")
    if items and isinstance(items, list):
        canvases = items

    elif "sequences" in data and data["sequences"]:
        canvases = data["sequences"][0].get("canvases", [])
    else:
        raise ValueError(f"No canvases found in manifest {url}")

    if not canvases:
        raise ValueError(f"Manifest contains 0 canvases: {url}")


    if seq < 0:
        seq = 0
    if seq >= len(canvases):
        seq = len(canvases) - 1

    canvas = canvases[seq]
    canvas_id = canvas.get("@id") or canvas.get("id")
    width = canvas.get("width") or canvas.get("height") or 8000
    height = canvas.get("height") or canvas.get("width") or 12000

    return canvas_id, width, height



def make_annotation(canvas_id, uniq, coords_px, label="Annotation", cluster=None, href=None):
    x = int(coords_px['x']); y = int(coords_px['y'])
    w = int(coords_px['w']); h = int(coords_px['h'])

    body = [{
        "type": "TextualBody",
        "format": "text/plain",
        "value": f"From {label} |"
    }]

    if cluster is not None:

        if isinstance(cluster, dict):
            cluster_id = cluster.get("id")
            cluster_count = cluster.get("count", "?")
        else:
            cluster_id = cluster
            cluster_count = None
        

    if cluster_id is not None:
        label_text = f"Cluster {cluster_id}"
    if cluster_count:
        label_text += f" ({cluster_count})"
    body.append({
        "type": "TextualBody",
        "format": "text/html",
        "value": f"<a href='{href}' target='_blank' rel='noopener'>{label_text}</a>|"
    })

    return {
        "type": "Annotation",
        "id": f"{canvas_id}#anno-{uniq}",
        "motivation": "commenting",
        "body": body,
        "target": f"{canvas_id}#xywh={x},{y},{w},{h}",
    }


@app.get("/annotations/<doc_id>.json")
def annotations_for_doc(doc_id):
    document = es.retrieve_document(doc_id)
    if not document or '_source' not in document:
        abort(404)

    src         = document['_source']
    corpus      = src.get('corpus')
    manifest_id = src.get('id')
    seq         = int(src.get('p1seq') or 0)
    page_image  = src.get('page_image')
    cluster_cur = src.get('cluster')
    cluster_url = f"https://clusters.viraltexts.org/cluster/{cluster_cur}"

    requested_canvas_id = request.args.get("canvasId")

    try:
        if corpus == 'ia':
            current_canvas_id, canvas_w, canvas_h = _ia_canvas_id_from_manifest(manifest_id, seq)
        elif corpus.startswith(('ca', 'acdc')):
            current_canvas_id, canvas_w, canvas_h = _loc_canvas_id_with_dims(
                src.get('series'),
                src.get('date'),
                src.get('ed'),
                seq
            )
        else:
            abort(400, f"Unsupported corpus '{corpus}' for annotations")
    except Exception as e:
        abort(400, f"Failed to resolve canvasId: {e}")

    if requested_canvas_id:
        current_canvas_id = requested_canvas_id

    if corpus.startswith(('ca', 'acdc')):
        p1iiif = src.get('p1iiif') or src.get('url') or ''
        manifest_prefix = p1iiif.rsplit(':', 1)[0] 
    else:
        manifest_prefix = manifest_id


    items = []

    page_boxes = es.get_boxes_for_manifest_page(manifest_prefix, seq=seq)


    if not page_boxes and page_image:
        pct = _parse_pct_from_page_image(page_image)
        if pct and canvas_w and canvas_h:
            items.append(make_annotation(
                current_canvas_id, f"pct-{seq}",
                {
                    'x': (pct['x'] / 100.0) * canvas_w,
                    'y': (pct['y'] / 100.0) * canvas_h,
                    'w': (pct['w'] / 100.0) * canvas_w,
                    'h': (pct['h'] / 100.0) * canvas_h,
                },
                label=src.get('source'),
                cluster=cluster_cur,
                href=cluster_url
            ))

    for i, box in enumerate(page_boxes, start=1):
        cluster_id = box["cluster"]
        cluster_count = es.get_cluster_count(cluster_id)
        cluster_url = url_for('get_cluster', cluster_id=cluster_id, _external=True)
        if box.get("es_id"):
            cluster_url = f"{cluster_url}?focus={box['es_id']}"
        items.append(make_annotation(
            current_canvas_id,
            f"box-{seq}-{i}",
            {"x": box["x"], "y": box["y"], "w": box["w"], "h": box["h"]},
            label=box["label"] or "Citation",
            cluster={"id": cluster_id, "count": cluster_count},
            href=cluster_url
        ))

    anno_page = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": url_for("annotations_for_doc", doc_id=doc_id, _external=True),
        "type": "AnnotationPage",
        "items": items,
    }

    resp = make_response(jsonify(anno_page))
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp



@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp    
    

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    # app.run(debug=True)
    app.run()