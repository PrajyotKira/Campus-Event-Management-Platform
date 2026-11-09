"""Authentication: register, login, logout, and the admin_required decorator.

Flask-Login remembers who is logged in (using a signed session cookie) and gives
us `current_user` in every view and template.
"""
import functools
import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

# All routes in this file start with /auth, e.g. /auth/login
bp = Blueprint("auth", __name__, url_prefix="/auth")

login_manager = LoginManager()
# Where to send people who try to open a page that needs a login.
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to see that page."
login_manager.login_message_category = "error"


class User(UserMixin):
    """A logged-in user, built from one row of the users table.

    UserMixin adds the properties Flask-Login needs (is_authenticated, get_id, ...).
    """

    def __init__(self, row):
        self.id = row["id"]
        self.name = row["name"]
        self.email = row["email"]
        self.role = row["role"]

    @property
    def is_admin(self):
        return self.role == "admin"


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login calls this on every request to turn the id stored in the
    session cookie back into a User object (or None if the user no longer exists)."""
    row = get_db().execute(
        "SELECT id, name, email, role FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return None
    return User(row)


def admin_required(view):
    """Decorator for admin-only pages.

    - not logged in  -> redirect to the login page
    - logged in, but not an admin -> 403 Forbidden
    """

    @functools.wraps(view)  # keep the original function's name for Flask's routing
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Create a new student account. Admin accounts are only made by setup.sh."""
    if current_user.is_authenticated:
        return redirect(url_for("events.list_events"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Basic checks before touching the database.
        error = None
        if not name:
            error = "Name is required."
        elif "@" not in email:
            error = "Please enter a valid email address."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."

        if error is None:
            conn = get_db()
            try:
                # The role is always 'student' here, so nobody can sign up as admin.
                conn.execute(
                    "INSERT INTO users (name, email, password_hash, role) "
                    "VALUES (?, ?, ?, 'student')",
                    (name, email, generate_password_hash(password)),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                # The UNIQUE constraint on users.email rejects a duplicate email.
                error = "An account with that email already exists."
            else:
                flash("Account created. Please log in.", "success")
                return redirect(url_for("auth.login"))

        flash(error, "error")

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("events.list_events"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        row = get_db().execute(
            "SELECT id, name, email, role, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        # check_password_hash hashes the typed password the same way and compares.
        # We give one message for both cases so attackers can't tell which emails exist.
        if row is None or not check_password_hash(row["password_hash"], password):
            flash("Invalid email or password.", "error")
        else:
            login_user(User(row))
            flash(f"Welcome, {row['name']}!", "success")
            return redirect(url_for("events.list_events"))

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))
