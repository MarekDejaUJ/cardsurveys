"""WSGI entry point: gunicorn wsgi:app"""
from cardsurveys import create_app

app = create_app()
