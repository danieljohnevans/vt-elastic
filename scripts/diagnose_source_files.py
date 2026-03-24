"""
Query old ES cluster for source_file distribution to understand data gaps.

Shows how many documents come from each data batch (Globus vs vt-clusters-20250623).

Usage:
    ES_HOST=https://es.viral-texts.software.ncsa.illinois.edu python diagnose_source_files.py
"""
from vt.elastic import elastic_client

es = elastic_client()

body = {
    "size": 0,
    "aggs": {
        "source_files": {
            "terms": {
                "field": "source_file.keyword",
                "size": 500
            }
        }
    }
}

resp = es.search(index="viral-texts", body=body)
buckets = resp["aggregations"]["source_files"]["buckets"]

print(f"{'Source file':<80} {'Count':>12}")
print("-" * 94)
total = 0
for b in buckets:
    print(f"{b['key']:<80} {b['doc_count']:>12,}")
    total += b["doc_count"]

other = resp["aggregations"]["source_files"].get("sum_other_doc_count", 0)
print(f"{'(other source files)':<80} {other:>12,}")
print(f"{'TOTAL':<80} {total + other:>12,}")
