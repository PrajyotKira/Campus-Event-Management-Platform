"""Database helpers: open/close the SQLite connection and set up the database.

We use Python's built-in sqlite3 module with raw SQL (no ORM).
"""
import os
import sqlite3

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db():
    """Return the database connection for the current request.

    The connection is stored in Flask's `g` object, so every query during one
    request reuses the same connection instead of opening a new one each time.
    """
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        # Row factory: rows behave like dicts, so we can write row["title"].
        g.db.row_factory = sqlite3.Row
        # SQLite ignores FOREIGN KEY rules unless this is switched on for each connection.
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    """Close the connection at the end of the request (if one was opened)."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    """Create all tables by running sql/schema.sql (drops existing tables first)."""
    conn = get_db()
    # current_app.root_path is the app/ folder; schema.sql is in ../sql/
    schema_path = os.path.join(current_app.root_path, "..", "sql", "schema.sql")
    with open(schema_path, encoding="utf-8") as f:
        conn.executescript(f.read())


@click.command("init-db")
def init_db_command():
    """CLI command: flask --app app init-db"""
    init_db()
    click.echo("    Database created at " + current_app.config["DATABASE"])


@click.command("create-admin")
@click.option("--name", default="Admin", help="Admin's display name")
@click.option("--email", default="admin@campus.local", help="Admin's login email")
@click.option("--password", default="admin123", help="Admin's password")
def create_admin_command(name, email, password):
    """CLI command: flask --app app create-admin --email ... --password ..."""
    conn = get_db()

    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()
    if existing is not None:
        click.echo(f"    Admin {email} already exists, skipping.")
        return

    # Store only a salted hash of the password, never the password itself.
    conn.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
        (name, email, generate_password_hash(password)),
    )
    conn.commit()
    click.echo(f"    Admin account created: {email}")


def init_app(app):
    """Connect the helpers above to the Flask app (called from create_app)."""
    app.teardown_appcontext(close_db)          # close the DB after every request
    app.cli.add_command(init_db_command)       # adds "flask init-db"
    app.cli.add_command(create_admin_command)  # adds "flask create-admin"
