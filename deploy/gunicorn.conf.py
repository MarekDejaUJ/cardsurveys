"""Gunicorn settings for Card Surveys.

The access log is off: the application stores no network addresses, and the
process log should not hold them either. Errors go to the journal.
"""
import os

bind = os.environ.get("CARDS_BIND", "127.0.0.1:8002")
workers = int(os.environ.get("CARDS_WORKERS", "2"))
threads = int(os.environ.get("CARDS_THREADS", "4"))
worker_class = "gthread"
timeout = 60
graceful_timeout = 30
accesslog = None
errorlog = "-"
loglevel = "warning"
forwarded_allow_ips = "127.0.0.1"
