import json
import os, os.path
import shutil
import sys
from vt.elastic import elastic_client

from elasticsearch.helpers import bulk
from elasticsearch.helpers.errors import BulkIndexError
from datetime import datetime

report_freq = 2000

# Load uid:begin -> Elasticsearch _id mapping (produced by export_id_map.py).
# Uses composite key because uid alone is not unique (identifies page, not passage).
# JSONL format: one {key: value} per line to handle 259M+ entries without OOM.
id_map_path = os.path.join(os.path.dirname(__file__), "uid_to_esid.jsonl")
id_map = {}
if os.path.exists(id_map_path):
    print(f"Loading uid:begin -> _id mappings from {id_map_path}...")
    with open(id_map_path, "r") as f:
        for line in f:
            id_map.update(json.loads(line))
    print(f"Loaded {len(id_map)} uid:begin -> _id mappings")
else:
    print("No uid_to_esid.jsonl found; new documents will get composite-key IDs.")

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
            uid_str = str(doc["uid"])
            begin_str = str(doc.get("begin", ""))
            composite_key = f"{uid_str}:{begin_str}"
            yield {
                "_index": "viral-texts",
                "_id": id_map.get(composite_key, composite_key),
                "_source": doc
            }


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
