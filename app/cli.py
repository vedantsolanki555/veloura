"""
Flask CLI commands — run with `flask <command>`.

Commands:
    make-admin <email>   Promote an existing registered user to admin.
    list-orders          (Step 4) List all orders — placeholder until orders exist.
"""

import click
from flask.cli import with_appcontext


@click.command("make-admin")
@click.argument("email")
@with_appcontext
def make_admin(email):
    """Turn an existing registered user into an admin (by email).

    Example:  flask make-admin you@example.com

    There is no hardcoded admin username or password anywhere in the app.
    You promote a normal account yourself from the terminal.
    """
    # Imported inside the function so the CLI loads fast and there are no
    # circular imports at startup.
    from app import db
    from app.models import User

    # Email is always stored lowercase — compare in lowercase too.
    user = User.query.filter(db.func.lower(User.email) == email.lower().strip()).first()

    if user is None:
        # Friendly error, exit code 1 so scripts can detect failure.
        raise click.ClickException(
            f"No user found with email '{email}'. "
            "Register the account first, then run make-admin again."
        )

    if user.is_admin:
        click.echo(f"{user.email} is already an admin.")
        return

    user.is_admin = True
    db.session.commit()
    click.echo(f"Done — {user.email} is now an admin. Log in at /login, then open /admin.")


def register_commands(app):
    """Attach our custom commands to the Flask app."""
    app.cli.add_command(make_admin)
