"""
WSGI entry point — the door gunicorn (and Render) use to start the app.

Local dev:  python wsgi.py
Production: gunicorn wsgi:app
"""

from app import create_app

# The actual Flask application object.
app = create_app()

if __name__ == "__main__":
    # Running with `python wsgi.py` starts Flask's built-in dev server.
    # Use gunicorn in production instead.
    app.run(host="127.0.0.1", port=5000)
