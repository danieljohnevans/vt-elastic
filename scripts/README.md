# Viral Texts Data Processing
This directory contains a number of scripts and Kubernetes configurations for processing and managing the Viral Texts dataset.

## The Workflow
The data processing workflow consists of the following steps:
1. Create the Index in Elasticsearch with the required mappings. This is done using the `create_index.py` script.
2. Distribute the JSON files among workers. This is done using the `distribute_json_files.py` script.
3. Ingest the data into Elasticsearch. This is done using the `ingest.py` script.

## Interaction with Kubernetes
The `busybox.yaml` file defines a Kubernetes pod that can be used to interact with the Kubernetes cluster. The pod has the `viral-texts` scripts and data mounted as volumes at `/data`.

The `ingest_job.yaml` file defines a Kubernetes job that can be used to ingest the data into Elasticsearch. The job runs multiple instances of the `ingest.py` script in parallel.


# Viral Texts Busybox
This is a simple Busybox container that can be used to perform basic operations in the Kubernetes cluster. It is based on the Python 3.10 image and has the viral texts scripts and data mounted as volumes at `/data`.

## Instructions
Install the pod using the following command:
```bash
kubectl apply -f taiga-busybox.yaml
```

You can then access the pod using the following command:
```bash
kubectl exec -it busybox-pod -- /bin/bash
```

# Elasticsearch Index Management Script

This script provides functionality to manage an Elasticsearch index named "viral-texts-test". It allows listing the current index mapping and creating a new index with predefined settings and mappings.

## Usage
The script can be run with two different commands:

1. List the current index mapping:
```bash
python script_name.py list
```

2. Create a new index (deleting the existing one if it already exists):
```bash
python script_name.py create
```

## Features

- **List Mapping**: Displays the current mapping of the "viral-texts-test" index in JSON format.
- **Create Index**:
- Checks if the index already exists and deletes it if it does.
- Creates a new index with predefined settings and mappings.
- Sets up 66 shards and 0 replicas.
- Defines a comprehensive mapping for various fields including text, keyword, date, boolean, and numeric types.

## Index Structure

The index is designed to store document metadata and content, with fields for:
- Source information (e.g., altSource, batch, sourceFile)
- Publication details (e.g., title, publisher, date)
- Geographical information (e.g., city, country, lat, lon)
- Document structure (e.g., page numbers, sections)
- Content (e.g., text, heading)
- Various identifiers and metrics

## Note

This script is designed for a specific use case and may need modifications to fit other Elasticsearch index management needs. Always ensure you have proper backups before manipulating production indices.

## Caution

The 'create' command will delete the existing index if it exists. Use with caution in production environments.


# JSON File Distributor

This Python script distributes JSON files from the current working directory into subdirectories named after workers. It takes the number of workers as a command-line argument and evenly distributes the JSON files among them.

## Features

- Creates subdirectories for each worker
- Evenly distributes JSON files among worker directories
- Handles cases where there are no JSON files or invalid input

## Usage

Create a shell inside the cluster with the Busybox and run the script from the command line there, providing the number of workers as an argument:
```bash
python distribute_json_files.py <number_of_workers>
```

Replace `<number_of_workers>` with a positive integer representing the number of worker subdirectories you want to create.

## How it works

1. The script checks for JSON files in the current directory.
2. It creates subdirectories named `worker_0`, `worker_1`, etc., up to the specified number of workers.
3. It calculates how many files should be distributed to each worker.
4. The script then moves the JSON files into the worker subdirectories, distributing them evenly.

## Example

If you have 10 JSON files in your current directory and you run:
```bash
python distribute_json_files.py 3
```

The script will create three subdirectories (`worker_0`, `worker_1`, `worker_2`) and distribute the JSON files among them, with 4 files in the first two directories and 2 in the last one.

## Notes

- The script will overwrite existing subdirectories with the same names.
- It's recommended to back up your JSON files before running this script.
- The script will print the moving operations to the console for verification.

## Error Handling

- If no JSON files are found, the script will display a message and exit.
- If an invalid number of workers is provided, the script will display an error message and exit.


# Elasticsearch Data Importer

This script processes JSON files from a specified directory and imports the data into an Elasticsearch index.

## Features

- Reads JSON files from a specified directory
- Imports data into an Elasticsearch index
- Tracks processing progress and reports statistics
- Moves processed files to a "processed" subdirectory

## Requirements

- Python 3.x
- Elasticsearch Python client
- Access to an Elasticsearch instance

## Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Configuration

Set the following environment variables:

- `ELASTIC_PASSWORD`: Password for the 'elastic' user in Elasticsearch
- `ELASTIC_URL`: URL of your Elasticsearch instance

## Usage

Run the script with the following command:

```bash
python ingest.py <directory>
```
Replace `<directory>` with the path to the directory containing the JSON files you want to process.

## How it works

1. The script connects to the Elasticsearch instance using the provided credentials.
2. It iterates through each JSON file in the specified directory.
3. For each file, it:
   - Reads the file line by line
   - Parses each line as a JSON object
   - Adds a 'source_file' field to each object
   - Imports the data into the "viral-texts-test" Elasticsearch index
   - Reports progress every 2000 records
4. After processing, it moves the file to a "processed" subdirectory.

## Output

The script provides progress updates, including:
- Number of records processed
- Processing time
- Input rate (records per second)
- Elasticsearch bulk import results

## Note

Ensure you have the necessary permissions to read from the input directory and write to the "processed" subdirectory.


# Data Ingestion Job

The ingest script can acheive greater throughput by running several in parallele. We use a kubernetes
job to acheive this parellelism.
The [ingest_job.yaml](ingest_job.yaml) defines a Kubernetes Job that runs a data ingestion script in parallel across multiple containers. It uses a Python container to execute the ingestion process and mounts an NFS volume to access and store data.

## Usage

1. Ensure your Kubernetes cluster has access to the required NFS volume.
2. Apply this configuration to your cluster using `kubectl apply -f <filename>.yaml`.
3. Monitor the job progress using `kubectl get jobs` and `kubectl get pods`.

## Notes

- The job creates 4 parallel containers, each running an instance of the ingestion script.
- Each container is assigned a unique index (0-3) via the `JOB_COMPLETION_INDEX` environment variable.
- The ingestion script is designed to handle parallel processing based on the provided index.
- Ensure that the NFS volume contains the necessary script files and virtual environment.
