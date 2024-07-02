import json
import os, os.path
import shutil
import sys
from vt.elastic import elastic_client

from elasticsearch.helpers import bulk
from elasticsearch.helpers.errors import BulkIndexError
from datetime import datetime

report_freq = 2000

def gendata(filename:str):
    with open(filename, "r") as f:
        tick = datetime.now()
        grand_tick = tick
        record_count = 0

        for l in f:
            record_count += 1
            if record_count % report_freq == 0:
                tock = datetime.now()
                print(f"Processed {record_count} records in {tock - tick}.")
                print(f"Total time: {tock - grand_tick}. Input rate: {record_count / (tock - grand_tick).total_seconds()} hertz.")
                tick = tock

            doc = json.loads(l)
            doc['source_file'] = filename
            yield {
                "_index": "search",
                "_source": doc
            }


# Password for the 'elastic' user generated by Elasticsearch
ELASTIC_PASSWORD = os.environ.get("ELASTIC_PASSWORD")
ELASTIC_URL = os.environ.get("ELASTIC_URL")

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <directory>")
    sys.exit(1)

data_dir = sys.argv[1]

# Create the client instance
es = elastic_client()

# Successful response!
print(es.info())

print(f"Processing files in {data_dir}...")

processed_directory = os.path.join(data_dir, "processed")
os.makedirs(processed_directory, exist_ok=True)

# Loop over each file in the directory
for filename in os.listdir(data_dir):
    if filename.endswith(".json"):
        print(f"Processing {filename}...")
        full_path = os.path.join(data_dir, filename)
        try:
            (success, info) = bulk(es, gendata(full_path), max_retries=4)
            shutil.move(full_path, os.path.join(processed_directory, filename))
            print(f"Processed {filename} with success={success} and info={info}")

        except BulkIndexError as e:
            print(f"Error processing {filename}: {e}")
            continue
