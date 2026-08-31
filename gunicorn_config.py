import os

bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8080')

# Threaded workers so a slow upstream (LOC image/manifest fetches) can't block
# the whole site. Threads share memory, so this adds concurrency without the
# per-process RAM cost of extra workers. 2 workers x 8 threads = 16 concurrent
# requests, most of them I/O-bound proxy calls that release the GIL on network.
worker_class = 'gthread'
workers = int(os.environ.get('GUNICORN_PROCESSES', '2'))
threads = int(os.environ.get('GUNICORN_THREADS', '8'))
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))

# We sit behind nginx (TLS terminated there); trust its forwarded proto so
# request.scheme / url_for(_external=True) produce https.
forwarded_allow_ips = '*'
secure_scheme_headers = {'X-Forwarded-Proto': 'https'}