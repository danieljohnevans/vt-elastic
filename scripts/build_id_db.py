"""Convert uid_to_esid.jsonl -> uid_to_esid.db (SQLite on-disk key-value store)."""
import json
import os
import sqlite3

scripts_dir = os.path.dirname(__file__)
jsonl_path = os.path.join(scripts_dir, "uid_to_esid.jsonl")
db_path = "/data/vt_data/uid_to_esid.db"

conn = sqlite3.connect(db_path)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=OFF")
conn.execute("CREATE TABLE IF NOT EXISTS id_map (key TEXT PRIMARY KEY, value TEXT)")

count = 0
batch = []
BATCH_SIZE = 100_000

with open(jsonl_path, "r") as f:
    for line in f:
        for k, v in json.loads(line).items():
            batch.append((k, v))
            count += 1
            if len(batch) >= BATCH_SIZE:
                conn.executemany("INSERT OR REPLACE INTO id_map VALUES (?, ?)", batch)
                conn.commit()
                batch.clear()
                if count % 5_000_000 == 0:
                    print(f"  {count:,} entries...")

if batch:
    conn.executemany("INSERT OR REPLACE INTO id_map VALUES (?, ?)", batch)
    conn.commit()

conn.close()
print(f"Built {db_path} with {count:,} entries")
