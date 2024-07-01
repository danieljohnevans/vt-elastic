import os
import sys
import json
import shutil
from math import ceil

def distribute_files(num_workers):
    # Get all JSON files in the current directory
    json_files = [f for f in os.listdir() if f.endswith('.json')]

    if not json_files:
        print("No JSON files found in the current directory.")
        return

    # Create worker directories
    for i in range(0, num_workers):
        worker_dir = f"worker_{i}"
        os.makedirs(worker_dir, exist_ok=True)

    # Calculate files per worker
    files_per_worker = ceil(len(json_files) / num_workers)

    # Distribute files
    for i, file in enumerate(json_files):
        worker_index = i // files_per_worker
        destination = f"worker_{worker_index}/{file}"
        shutil.move(file, destination)
        print(f"Moved {file} to {destination}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <number_of_workers>")
        sys.exit(1)

    try:
        num_workers = int(sys.argv[1])
        if num_workers <= 0:
            raise ValueError
    except ValueError:
        print("Please provide a positive integer for the number of workers.")
        sys.exit(1)

    distribute_files(num_workers)
