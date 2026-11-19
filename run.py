"""Development server; on a server use Gunicorn with wsgi:app."""
from cardsurveys import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False)
