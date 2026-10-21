# Veloura

Premium clothing store website. Built with Python Flask, SQLAlchemy, PostgreSQL, and Jinja2 templates.

## Project status

- **Step 1 (done):** project setup, database models, seed data, simple home page.
- Later steps: design, cart, checkout, admin panel.

## Requirements

- Python 3.12+

## How to run (local development)

```bash
# 1. Create and activate a virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your .env file from the example
copy .env.example .env
# Then open .env and set SECRET_KEY to a long random string.

# 4. Create tables + seed data (safe to re-run; skips if data already exists)
python seed.py

# 5. Start the development server
python wsgi.py
```

Open <http://127.0.0.1:5000/> in your browser. You should see "Veloura".

## Configuration (environment variables)

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask session signing key. Required. |
| `DATABASE_URL` | PostgreSQL connection string. If unset, app uses SQLite locally (`instance/veloura.db`) — **dev fallback only, do not use SQLite in production**. |
| `CLOUDINARY_URL` | Cloudinary credentials for product image uploads (admin panel). Format: `cloudinary://API_KEY:API_SECRET@CLOUD_NAME` |
| `WHATSAPP_NUMBER` | Digits-only WhatsApp number (country code, no `+`) for the WhatsApp order buttons. |
| `FLASK_ENV` | `development` or `production`. |

Secrets live only in environment variables (via `.env` locally, Render dashboard in production). Never hardcode them.

## Product image uploads (important)

Admin product images are saved in **one of two places**:

1. **Cloudinary (production / recommended).** If `CLOUDINARY_URL` is set in
   `.env`, every uploaded image goes to Cloudinary and the app stores the
   secure URL + `public_id` in the database.
2. **Local fallback (development).** If `CLOUDINARY_URL` is **not** set, images
   are saved to `app/static/uploads/` instead. This keeps the admin panel
   working locally with no Cloudinary account.

Uploaded files in `app/static/uploads/` are **never committed to git**
(`.gitignore` covers the folder) and the folder is safe to delete at any time.
Only JPG, PNG and WEBP images up to 5 MB each are accepted.

## Deploy to Render

1. Push this repository to GitHub.
2. On Render: create a new Web Service, point it at the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn wsgi:app`
5. Add environment variables: `SECRET_KEY`, `DATABASE_URL` (Render Postgres), `CLOUDINARY_URL`, `FLASK_ENV=production`.

## Project structure

```
Veloura/
├── app/
│   ├── __init__.py      # App factory — creates the Flask app
│   ├── models.py        # Database models (tables)
│   ├── routes/          # URL handlers (Blueprints)
│   │   ├── __init__.py
│   │   └── main.py      # Home page route
│   ├── templates/       # Jinja2 HTML templates
│   │   └── home.html
│   └── static/          # CSS, JS, images served to the browser
│       ├── css/style.css
│       └── js/main.js
├── config.py            # App configuration (reads env vars)
├── wsgi.py              # Entry point for gunicorn / python wsgi.py
├── seed.py              # Fills the database with sample data
├── requirements.txt     # Python packages
├── .env.example         # Template for your .env file
└── .gitignore
```
