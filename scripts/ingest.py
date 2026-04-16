import json
import os, os.path
import shutil
import sqlite3
import sys
from vt.elastic import elastic_client

from elasticsearch.helpers import bulk
from elasticsearch.helpers.errors import BulkIndexError
from datetime import datetime

report_freq = 2000

# Open uid:begin -> _id mapping as SQLite database.
# Built by build_id_db.py from uid_to_esid.jsonl.
db_path = "/data/vt_data/uid_to_esid.db"
id_db = None
if os.path.exists(db_path):
    id_db = sqlite3.connect(db_path)
    id_db.execute("PRAGMA journal_mode=WAL")
    print(f"Opened id mapping database at {db_path}")
else:
    print("No uid_to_esid.db found; new documents will get composite-key IDs.")

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

            try:
                doc = json.loads(l)
            except json.JSONDecodeError as e:
                print(f"Skipping bad JSON on line {record_count}: {e}")
                continue
            doc['source_file'] = filename
            uid_str = str(doc["uid"])
            begin_str = str(doc.get("begin", ""))
            composite_key = f"{uid_str}:{begin_str}"
            if id_db:
                row = id_db.execute("SELECT value FROM id_map WHERE key = ?", (composite_key,)).fetchone()
                es_id = row[0] if row else composite_key
            else:
                es_id = composite_key
            yield {
                "_index": "viral-texts",
                "_id": es_id,
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
