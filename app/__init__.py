"""Application factory for the Campus Event Management Platform.

Flask calls create_app() when you run:  flask --app app run
Building the app inside a function (instead of at import time) lets the tests
create a fresh app with a separate test database.
"""
import os

from flask import Flask, render_template

from . import db


def create_app(test_config=None):
    # instance_relative_config=True: the "instance/" folder (next to app/) holds
    # files that belong to this machine only, like the SQLite database.
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        # SECRET_KEY signs the session cookie. Use a real secret outside development.
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        DATABASE=os.path.join(app.instance_path, "campus.db"),
    )

    # Tests pass their own settings (e.g. a temporary database path).
    if test_config is not None:
        app.config.update(test_config)

    # Make sure the instance/ folder exists so SQLite can create the file there.
    os.makedirs(app.instance_path, exist_ok=True)

    # Register database helpers and the init-db / create-admin commands.
    db.init_app(app)

    @app.route("/")
    def index():
        """Homepage: shows a few counts to prove the database connection works."""
        conn = db.get_db()
        stats = {
            "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "venues": conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0],
            "students": conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'student'"
            ).fetchone()[0],
        }
        return render_template("index.html", stats=stats)

    return app
