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

out_path = os.path.join(os.path.dirname(__file__), "uid_to_esid.jsonl")

print("Scrolling through viral-texts index...")
with open(out_path, "w") as f:
    for hit in scan(es, index="viral-texts", _source=["uid", "begin"], scroll="30m"):
        uid = str(hit["_source"]["uid"])
        begin = str(hit["_source"].get("begin", ""))
        key = f"{uid}:{begin}"

        f.write(json.dumps({key: hit["_id"]}) + "\n")

        # Also add float64-truncated uid variant
        try:
            uid_int = int(uid)
            truncated = str(int(Decimal(repr(float(uid_int)))))
            if truncated != uid:
                trunc_key = f"{truncated}:{begin}"
                f.write(json.dumps({trunc_key: hit["_id"]}) + "\n")
        except (ValueError, OverflowError):
            pass

print(f"Export complete -> {out_path}")