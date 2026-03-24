"""Convert uid_to_esid.jsonl -> uid_to_esid.db (dbm on-disk key-value store)."""
import dbm
import json
import os

scripts_dir = os.path.dirname(__file__)
jsonl_path = os.path.join(scripts_dir, "uid_to_esid.jsonl")
db_path = os.path.join(scripts_dir, "uid_to_esid")

count = 0
with dbm.open(db_path, "n") as db, open(jsonl_path, "r") as f:
    for line in f:
        for k, v in json.loads(line).items():
            db[k] = v
            count += 1
            if count % 5_000_000 == 0:
                print(f"  {count:,} entries...")

print(f"Built {db_path}.db with {count:,} entries")
