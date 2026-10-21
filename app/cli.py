"""
Flask CLI commands — run with `flask <command>`.

Commands:
    make-admin <email>   Promote an existing registered user to admin.
    list-orders          List every COD order (newest first).
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


@click.command("list-orders")
@with_appcontext
def list_orders():
    """List all COD orders (newest first): number, name, phone, total, status, items."""
    from app.models import Order

    orders = Order.query.order_by(Order.created_at.desc()).all()

    if not orders:
        click.echo("No orders yet.")
        return

    for order in orders:
        items = ", ".join(
            f"{item.quantity}x {item.product_name} ({item.size}/{item.colour})"
            for item in order.items
        ) or "(no items)"
        click.echo(
            f"{order.order_number} | {order.customer_name} | {order.phone} | "
            f"₹{order.total} | {order.status} | {items}"
        )
    click.echo(f"\n{len(orders)} order(s) total.")


def register_commands(app):
    """Attach our custom commands to the Flask app."""
    app.cli.add_command(make_admin)
    app.cli.add_command(list_orders)
