"""Event pages for everyone: list with search/filters and detail page.
Plus, for logged-in students: register, cancel and "My registrations"."""
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .db import get_db

# No url_prefix: routes write their full path, because /my-registrations
# does not start with /events.
bp = Blueprint("events", __name__)

# The fixed list of event categories (also used by admin.py and seed.py).
CATEGORIES = ["Technical", "Cultural", "Sports", "Workshop", "Seminar"]


def now_string():
    """Current time in the same 'YYYY-MM-DD HH:MM' format we store in the database."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def get_event(event_id):
    """Return one event with its venue, organiser and seats left, or None.

    LEFT JOIN keeps events with zero registrations (COUNT(r.id) is then 0).
    """
    return get_db().execute(
        "SELECT e.id, e.title, e.description, e.category, e.start_time, e.end_time, "
        "       e.capacity, v.name AS venue_name, v.location AS venue_location, "
        "       u.name AS organiser, "
        "       e.capacity - COUNT(r.id) AS seats_left "
        "FROM events e "
        "JOIN venues v ON v.id = e.venue_id "
        "JOIN users u ON u.id = e.created_by "
        "LEFT JOIN registrations r ON r.event_id = e.id "
        "WHERE e.id = ? "
        "GROUP BY e.id",
        (event_id,),
    ).fetchone()


def is_registered(user_id, event_id):
    """True if this user already has a registration for this event."""
    row = get_db().execute(
        "SELECT 1 FROM registrations WHERE user_id = ? AND event_id = ?",
        (user_id, event_id),
    ).fetchone()
    return row is not None


def build_search_sql(keyword="", category="", venue_id=None, date_from="", date_to=""):
    """Build the search query for the given filters (an empty filter is ignored).

    Returns (sql, params). Kept separate from running it so profiling/explain.py
    can show the query plan of exactly the same SQL.
    """
    # Build the WHERE clause piece by piece.
    # `conditions` only ever holds fixed SQL text written by us; every value the
    # user typed goes into `params` and reaches SQLite through a ? placeholder.
    # That is what protects us from SQL injection.
    conditions = ["e.start_time >= ?"]  # only upcoming events
    params = [now_string()]

    if keyword:
        conditions.append("(e.title LIKE ? OR e.description LIKE ?)")
        pattern = f"%{keyword}%"  # % means "any text" in LIKE
        params.extend([pattern, pattern])
    if category:
        conditions.append("e.category = ?")
        params.append(category)
    if venue_id:
        conditions.append("e.venue_id = ?")
        params.append(venue_id)
    if date_from:
        # '2026-11-20' <= '2026-11-20 10:00' as text, so this includes that whole day.
        conditions.append("e.start_time >= ?")
        params.append(date_from)
    if date_to:
        # Add the last minute of the day so events on date_to are included.
        conditions.append("e.start_time <= ?")
        params.append(date_to + " 23:59")

    # GROUP BY e.id gives one row per event, so COUNT counts that event's registrations.
    sql = (
        "SELECT e.id, e.title, e.category, e.start_time, e.end_time, e.capacity, "
        "       v.name AS venue_name, "
        "       e.capacity - COUNT(r.id) AS seats_left "
        "FROM events e "
        "JOIN venues v ON v.id = e.venue_id "
        "LEFT JOIN registrations r ON r.event_id = e.id "
        "WHERE " + " AND ".join(conditions) + " "
        "GROUP BY e.id "
        "ORDER BY e.start_time"
    )
    return sql, params


def search_events(keyword="", category="", venue_id=None, date_from="", date_to=""):
    """Return upcoming events matching the given filters.

    A plain function (not a route) so it can be tested and profiled directly.
    """
    sql, params = build_search_sql(keyword, category, venue_id, date_from, date_to)
    return get_db().execute(sql, params).fetchall()


@bp.route("/events/")
def list_events():
    """List upcoming events, optionally filtered by the search form.

    The form uses GET, so the filters appear in the URL, for example
    /events/?q=python&category=Workshop
    """
    # Read the filter values from the URL. type=int turns bad input into None.
    keyword = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    venue_id = request.args.get("venue_id", type=int)
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    events = search_events(keyword, category, venue_id, date_from, date_to)
    venues = get_db().execute("SELECT id, name FROM venues ORDER BY name").fetchall()

    # Send the current filter values back so the form keeps what the user typed.
    filters = {
        "q": keyword,
        "category": category,
        "venue_id": venue_id,
        "date_from": date_from,
        "date_to": date_to,
    }
    return render_template(
        "events/list.html",
        events=events,
        venues=venues,
        categories=CATEGORIES,
        filters=filters,
    )


@bp.route("/events/<int:event_id>")
def event_detail(event_id):
    """Show one event. <int:event_id> means the URL must end in a number."""
    event = get_event(event_id)
    if event is None:
        abort(404)

    # Whether to show the Register or the Cancel button.
    registered = False
    if current_user.is_authenticated:
        registered = is_registered(current_user.id, event_id)

    return render_template(
        "events/detail.html",
        event=event,
        is_registered=registered,
        has_started=event["start_time"] <= now_string(),
    )


@bp.route("/events/<int:event_id>/register", methods=["POST"])
@login_required
def register_for_event(event_id):
    """A student signs up for an event (POST only, from the button on the detail page)."""
    event = get_event(event_id)
    if event is None:
        abort(404)

    # Check every reason to refuse, in order, and explain which one applied.
    if current_user.is_admin:
        flash("Admins cannot register for events.", "error")
    elif event["start_time"] <= now_string():
        flash("This event has already started.", "error")
    elif is_registered(current_user.id, event_id):
        flash("You are already registered for this event.", "error")
    elif event["seats_left"] <= 0:
        flash("Sorry, this event is full.", "error")
    else:
        conn = get_db()
        # registered_at is filled in automatically by its DEFAULT in schema.sql.
        conn.execute(
            "INSERT INTO registrations (user_id, event_id) VALUES (?, ?)",
            (current_user.id, event_id),
        )
        conn.commit()
        flash(f"You are registered for {event['title']}.", "success")

    return redirect(url_for("events.event_detail", event_id=event_id))


@bp.route("/events/<int:event_id>/cancel", methods=["POST"])
@login_required
def cancel_registration(event_id):
    """A student removes their registration (only before the event starts)."""
    event = get_event(event_id)
    if event is None:
        abort(404)

    if event["start_time"] <= now_string():
        flash("You cannot cancel after the event has started.", "error")
    else:
        conn = get_db()
        cursor = conn.execute(
            "DELETE FROM registrations WHERE user_id = ? AND event_id = ?",
            (current_user.id, event_id),
        )
        conn.commit()
        # rowcount = how many rows the DELETE removed (0 means there was nothing to cancel).
        if cursor.rowcount == 0:
            flash("You were not registered for this event.", "error")
        else:
            flash(f"Your registration for {event['title']} was cancelled.", "success")

    # The cancel button exists on two pages; go back to the one it came from.
    if request.form.get("return_to") == "my":
        return redirect(url_for("events.my_registrations"))
    return redirect(url_for("events.event_detail", event_id=event_id))


@bp.route("/my-registrations")
@login_required
def my_registrations():
    """Upcoming events the logged-in student is registered for."""
    events = get_db().execute(
        "SELECT e.id, e.title, e.category, e.start_time, e.end_time, "
        "       v.name AS venue_name, r.registered_at "
        "FROM registrations r "
        "JOIN events e ON e.id = r.event_id "
        "JOIN venues v ON v.id = e.venue_id "
        "WHERE r.user_id = ? AND e.start_time >= ? "
        "ORDER BY e.start_time",
        (current_user.id, now_string()),
    ).fetchall()
    return render_template("events/my_registrations.html", events=events)
