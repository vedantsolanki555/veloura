"""
Gunicorn configuration (Step 6 Part 5).

Gunicorn auto-loads ./gunicorn.conf.py when it starts, both locally
(`gunicorn wsgi:app`) and on Render — no flags needed in the start command.

Render free plan: 0.1 CPU / 512 MB RAM — 2 sync workers is a safe fit.
Render also injects WEB_CONCURRENCY, which overrides the worker count.
"""

import os

# Render tells us which port to listen on; it defaults to 8000 locally.
bind = "0.0.0.0:" + os.environ.get("PORT", "8000")

# Workers: 2 fits comfortably in 512 MB. Render can override via
# WEB_CONCURRENCY (its standard variable for worker counts).
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))

# Seconds before a worker is killed and restarted (slow request protection).
timeout = 60
graceful_timeout = 30

# Log to stdout/stderr — Render shows these in the service "Logs" tab.
# Never log form values, passwords or tokens (our app does not).
accesslog = "-"
errorlog = "-"
loglevel = "info"
