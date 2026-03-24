"""
Export composite-key -> Elasticsearch _id mapping from the current index.

uid alone is NOT unique — it identifies the source page, not the passage.
We use uid:begin as a composite key to uniquely identify each document.

Run this BEFORE reindexing so that ingest.py can preserve existing
document IDs (which are referenced in published works).

Usage:
    python export_id_map.py

Output:
    uid_to_esid.json in the same directory as this script.
"""

import json
import os
from decimal import Decimal
from elasticsearch.helpers import scan
from vt.elastic import elastic_client

es = elastic_client()
id_map = {}

print("Scrolling through viral-texts index...")
for hit in scan(es, index="viral-texts", _source=["uid", "begin"], scroll="30m"):
    uid = str(hit["_source"]["uid"])
    begin = str(hit["_source"].get("begin", ""))
    key = f"{uid}:{begin}"
    id_map[key] = hit["_id"]

    # Also add float64-truncated uid variant for Globus data compatibility
    try:
        uid_int = int(uid)
        truncated = str(int(Decimal(repr(float(uid_int)))))
        if truncated != uid:
            trunc_key = f"{truncated}:{begin}"
            if trunc_key not in id_map:
                id_map[trunc_key] = hit["_id"]
    except (ValueError, OverflowError):
        pass

out_path = os.path.join(os.path.dirname(__file__), "uid_to_esid.json")
with open(out_path, "w") as f:
    json.dump(id_map, f)

print(f"Exported {len(id_map)} uid:begin -> _id mappings to {out_path}")
