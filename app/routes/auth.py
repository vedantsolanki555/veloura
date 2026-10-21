"""
Auth blueprint: customer account pages.

Routes:
    /register   Sign up (name, email, phone, password + confirm)
    /login      Log in (with rate limit + generic error message)
    /logout     Log out (POST only, CSRF protected)
    /account    Profile + "My orders" placeholder (real orders in Feature 3)
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from time import monotonic

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, ValidationError

from app import db, login_manager
from app.models import User

auth_bp = Blueprint("auth", __name__)


# ---------- forms ----------

def validate_email_format(_form, field):
    """Simple email check: must contain one @ and a dot after it.

    WTForms' built-in Email() rejects valid local addresses like
    admin@veloura.local (no public TLD), so we use this lighter check.
    """
    value = (field.data or "").strip()
    if value.count("@") != 1 or "." not in value.split("@")[-1]:
        raise ValidationError("Enter a valid email address.")


class RegisterForm(FlaskForm):
    """Sign-up form. Server-side validation — never trust the browser."""

    name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), validate_email_format, Length(max=120)])
    phone = StringField("Phone (10-digit mobile)", validators=[DataRequired(), Length(min=10, max=20)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=256)])
    confirm = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords do not match.")])
    submit = SubmitField("Create account")

    def validate_email(self, field):
        """Reject a second account with the same email (case-insensitive)."""
        if User.query.filter(db.func.lower(User.email) == field.data.lower()).first():
            raise ValidationError("An account with this email already exists.")

    def validate_phone(self, field):
        digits = "".join(ch for ch in field.data if ch.isdigit())
        if len(digits) < 10 or len(digits) > 15:
            raise ValidationError("Enter a valid phone number (10–15 digits).")


class LoginForm(FlaskForm):
    """Log-in form. The error message is always generic on purpose."""

    email = StringField("Email", validators=[DataRequired(), validate_email_format, Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


# ---------- login rate limit ----------
# 5 failed tries per 15 minutes per (IP + email). In-memory is fine for one
# process (local dev / single gunicorn worker). Key = "ip|email".
_failed_attempts = defaultdict(list)  # key -> list of monotonic() timestamps
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 15 * 60  # seconds


def _rate_limited(key):
    """True if this key has failed too many times in the last 15 minutes."""
    now = monotonic()
    recent = [t for t in _failed_attempts[key] if now - t < _RATE_LIMIT_WINDOW]
    _failed_attempts[key] = recent
    return len(recent) >= _RATE_LIMIT_MAX


def _record_failure(key):
    _failed_attempts[key].append(monotonic())


def _clear_failures(key):
    _failed_attempts.pop(key, None)


# ---------- helpers ----------

def _safe_next(target):
    """Only follow redirects to our own site.

    Accepts same-site relative paths like "/shop" or "/account".
    Rejects absolute URLs ("https://evil.com") and protocol-relative ones
    ("//evil.com") so the login form cannot be used as an open redirect.
    """
    if not target:
        return None
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    return target


# ---------- routes ----------

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Create a new customer account, then log the user in."""
    if current_user.is_authenticated:
        return redirect(url_for("auth.account"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data.strip(),
            email=form.email.data.strip().lower(),
            phone="".join(ch for ch in form.phone.data if ch.isdigit()),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Welcome to Veloura! Your account is ready.", "success")
        return redirect(url_for("auth.account"))

    return render_template("auth/register.html", form=form, title="Register")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Log in an existing customer."""
    if current_user.is_authenticated:
        return redirect(url_for("auth.account"))

    form = LoginForm()
    # Key combines IP + email so one attacker cannot lock out everyone.
    rate_key = f"{request.remote_addr}|{form.email.data.lower() if form.email.data else ''}"

    if form.validate_on_submit():
        if _rate_limited(rate_key):
            flash("Too many failed attempts. Please try again in 15 minutes.", "error")
            return render_template("auth/login.html", form=form, title="Log in", next=request.args.get("next", ""))

        user = User.query.filter(db.func.lower(User.email) == form.email.data.lower()).first()

        # Always the same generic message — never reveal which half is wrong.
        if user is None or not user.check_password(form.password.data):
            _record_failure(rate_key)
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html", form=form, title="Log in", next=request.args.get("next", ""))

        _clear_failures(rate_key)
        login_user(user)
        flash(f"Welcome back, {user.first_name}!", "success")

        # "next" must point back into this site, nowhere else.
        next_page = _safe_next(request.args.get("next")) or url_for("auth.account")
        return redirect(next_page)

    return render_template("auth/login.html", form=form, title="Log in", next=request.args.get("next", ""))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Log out. POST-only so a stray link or image cannot log users out."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))


@auth_bp.route("/account")
@login_required
def account():
    """Profile page + the customer's own orders (Feature 3)."""
    from app.models import Order

    orders = (
        Order.query.filter_by(user_id=current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    return render_template(
        "auth/account.html",
        title="My account",
        orders=orders,
        now=datetime.now(timezone.utc),
    )


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login calls this on every request to restore the session user."""
    return db.session.get(User, int(user_id))
