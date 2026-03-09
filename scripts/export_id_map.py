"""
Export a uid -> Elasticsearch _id mapping from the current index.

Run this BEFORE reindexing so that ingest.py can preserve existing
document IDs (which are referenced in published works).

Usage:
    python export_id_map.py

Output:
    uid_to_esid.json in the same directory as this script.
"""

import json
import os
from elasticsearch.helpers import scan
from vt.elastic import elastic_client

es = elastic_client()
id_map = {}

print("Scrolling through viral-texts index...")
for hit in scan(es, index="viral-texts", _source=["uid"], scroll="5m"):
    uid = str(hit["_source"]["uid"])
    id_map[uid] = hit["_id"]

out_path = os.path.join(os.path.dirname(__file__), "uid_to_esid.json")
with open(out_path, "w") as f:
    json.dump(id_map, f)

print(f"Exported {len(id_map)} uid -> _id mappings to {out_path}")
