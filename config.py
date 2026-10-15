"""
App configuration.

Everything secret (SECRET_KEY, DATABASE_URL, CLOUDINARY_URL) is read from
environment variables. Locally those come from the .env file (loaded in
app/__init__.py). On Render they are set in the dashboard.

NEVER hardcode secrets in this file or any other file in the project.
"""

import os

# Load the .env file if it exists (local development).
# python-dotenv ignores the error if the file is missing (e.g. on Render).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    """Base config shared by every environment."""

    # Flask needs a secret key to sign session cookies.
    # The fallback below is ONLY for local development so the app still starts
    # if you forget to create .env. In production this must come from the env var.
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-insecure-secret-key"

    # Database URL.
    # Production: DATABASE_URL must point to PostgreSQL (e.g. Render Postgres).
    # Local dev: if DATABASE_URL is not set, fall back to a local SQLite file.
    # SQLite is a single file database — fine for development, NOT for production.
    _database_url = os.environ.get("DATABASE_URL")
    if _database_url:
        SQLALCHEMY_DATABASE_URI = _database_url
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///veloura.db"  # file saved in instance/veloura.db

    # Silences a SQLAlchemy warning we don't need. Standard setting for Flask apps.
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    """Settings used when FLASK_ENV=development (default locally)."""

    DEBUG = True


class ProductionConfig(Config):
    """Settings used when FLASK_ENV=production (on Render)."""

    DEBUG = False


# Map the FLASK_ENV value to the right config class.
CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    """Return the config class matching the current FLASK_ENV."""
    env = os.environ.get("FLASK_ENV", "development")
    return CONFIG_MAP.get(env, DevelopmentConfig)
