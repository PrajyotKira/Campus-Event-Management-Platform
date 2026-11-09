"""Application factory for the Campus Event Management Platform.

Flask calls create_app() when you run:  flask --app app run
Building the app inside a function (instead of at import time) lets the tests
create a fresh app with a separate test database.
"""
import os

from flask import Flask, render_template

from . import admin, auth, db, events, seed


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
    # Add the "flask seed" command.
    app.cli.add_command(seed.seed_command)

    # Flask-Login: keeps track of the logged-in user.
    auth.login_manager.init_app(app)

    # Blueprints: each one is a group of related routes in its own file.
    app.register_blueprint(auth.bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(admin.bp)

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

    # Friendly error pages instead of Flask's plain default ones.
    @app.errorhandler(403)
    def forbidden(error):
        return render_template(
            "error.html", code=403, message="You are not allowed to view this page."
        ), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template(
            "error.html", code=404, message="That page does not exist."
        ), 404

    return app
