"""Event browsing for everyone: the list with search/filters, and the detail page."""
from datetime import datetime

from flask import Blueprint, abort, render_template, request

from .db import get_db

# All routes in this file start with /events
bp = Blueprint("events", __name__, url_prefix="/events")

# The fixed list of event categories (also used by seed.py).
CATEGORIES = ["Technical", "Cultural", "Sports", "Workshop", "Seminar"]


def now_string():
    """Current time in the same 'YYYY-MM-DD HH:MM' format we store in the database."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@bp.route("/")
def list_events():
    """List upcoming events, optionally filtered by the search form.

    The form uses GET, so the filters appear in the URL, for example
    /events/?q=python&category=Workshop
    """
    # 1. Read the filter values from the URL. type=int turns bad input into None.
    keyword = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    venue_id = request.args.get("venue_id", type=int)
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    # 2. Build the WHERE clause piece by piece.
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

    # 3. LEFT JOIN keeps events with zero registrations (COUNT(r.id) is then 0).
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

    conn = get_db()
    events = conn.execute(sql, params).fetchall()
    venues = conn.execute("SELECT id, name FROM venues ORDER BY name").fetchall()

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


@bp.route("/<int:event_id>")
def event_detail(event_id):
    """Show one event. <int:event_id> means the URL must end in a number."""
    event = get_db().execute(
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

    if event is None:
        abort(404)
    return render_template("events/detail.html", event=event)
