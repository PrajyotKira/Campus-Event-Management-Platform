"""Admin-only pages: dashboard, venue and event management, participant lists.

Every route has @admin_required: students get 403, visitors are sent to log in.
Pages that change data only accept POST, so a plain link can never delete anything.
"""
import csv
import io
from datetime import datetime

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .auth import admin_required
from .db import get_db
from .events import CATEGORIES, now_string

# All routes in this file start with /admin
bp = Blueprint("admin", __name__, url_prefix="/admin")


# ======================= Helper functions =======================

def to_db_time(value):
    """Convert an HTML datetime-local value ('2026-11-20T14:30') into our database
    format ('2026-11-20 14:30'). Returns None if it is not a valid date and time."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None
    return parsed.strftime("%Y-%m-%d %H:%M")


def find_clash(venue_id, start_time, end_time, ignore_event_id=None):
    """Return the first event at this venue whose time overlaps [start_time, end_time),
    or None if the venue is free.

    Two time ranges overlap when each one starts before the other one ends:
        other.start_time < new end   AND   other.end_time > new start
    Events that only touch (one ends exactly when the next starts) do not clash.

    When editing, ignore_event_id is the event being edited, so it is not
    reported as clashing with itself.
    """
    sql = (
        "SELECT id, title, start_time, end_time FROM events "
        "WHERE venue_id = ? AND start_time < ? AND end_time > ?"
    )
    params = [venue_id, end_time, start_time]
    if ignore_event_id is not None:
        sql += " AND id != ?"
        params.append(ignore_event_id)
    return get_db().execute(sql + " LIMIT 1", params).fetchone()


def read_event_form(form, event_id=None):
    """Check the submitted event form.

    Returns (values, None) when everything is valid, or (None, error_message).
    event_id is given when editing an existing event.
    """
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    category = form.get("category", "")
    venue_id = form.get("venue_id", type=int)   # None if missing or not a number
    capacity = form.get("capacity", type=int)
    start_time = to_db_time(form.get("start_time", ""))
    end_time = to_db_time(form.get("end_time", ""))

    if not title:
        return None, "Title is required."
    if category not in CATEGORIES:
        return None, "Please choose a category."
    if start_time is None or end_time is None:
        return None, "Please enter a valid start and end time."
    # Same-format text compares in time order, so this works on the strings.
    if end_time <= start_time:
        return None, "The event must end after it starts."
    if capacity is None or capacity <= 0:
        return None, "Capacity must be a whole number greater than 0."

    conn = get_db()
    venue = conn.execute(
        "SELECT id, name, capacity FROM venues WHERE id = ?", (venue_id,)
    ).fetchone()
    if venue is None:
        return None, "Please choose a venue."
    if capacity > venue["capacity"]:
        return None, (f"Capacity ({capacity}) cannot be more than the capacity of "
                      f"{venue['name']} ({venue['capacity']}).")

    if event_id is not None:
        # Don't allow shrinking an event below the number of people already registered.
        registered = conn.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id = ?", (event_id,)
        ).fetchone()[0]
        if capacity < registered:
            return None, f"{registered} students are already registered, so capacity cannot be lower."

    clash = find_clash(venue_id, start_time, end_time, ignore_event_id=event_id)
    if clash is not None:
        return None, (f"{venue['name']} is already booked for '{clash['title']}' "
                      f"({clash['start_time']} to {clash['end_time']}).")

    values = {
        "title": title,
        "description": description,
        "category": category,
        "venue_id": venue_id,
        "start_time": start_time,
        "end_time": end_time,
        "capacity": capacity,
    }
    return values, None


def read_venue_form(form, venue_id=None):
    """Check the submitted venue form. Returns (values, None) or (None, error)."""
    name = form.get("name", "").strip()
    location = form.get("location", "").strip()
    capacity = form.get("capacity", type=int)

    if not name:
        return None, "Venue name is required."
    if not location:
        return None, "Location is required."
    if capacity is None or capacity <= 0:
        return None, "Capacity must be a whole number greater than 0."

    if venue_id is not None:
        # An existing event may not be bigger than its venue.
        biggest = get_db().execute(
            "SELECT MAX(capacity) FROM events WHERE venue_id = ?", (venue_id,)
        ).fetchone()[0]
        if biggest is not None and capacity < biggest:
            return None, f"An event here has capacity {biggest}, so the venue cannot be smaller."

    return {"name": name, "location": location, "capacity": capacity}, None


def get_participants(event_id):
    """Students registered for an event, earliest registration first."""
    return get_db().execute(
        "SELECT u.name, u.email, r.registered_at "
        "FROM registrations r "
        "JOIN users u ON u.id = r.user_id "
        "WHERE r.event_id = ? "
        "ORDER BY r.registered_at",
        (event_id,),
    ).fetchall()


# ======================= Dashboard =======================

@bp.route("/")
@admin_required
def dashboard():
    # One query with several sub-queries, each counting one thing.
    counts = get_db().execute(
        "SELECT (SELECT COUNT(*) FROM events) AS events, "
        "       (SELECT COUNT(*) FROM events WHERE start_time >= ?) AS upcoming, "
        "       (SELECT COUNT(*) FROM venues) AS venues, "
        "       (SELECT COUNT(*) FROM users WHERE role = 'student') AS students, "
        "       (SELECT COUNT(*) FROM registrations) AS registrations",
        (now_string(),),
    ).fetchone()
    return render_template("admin/dashboard.html", counts=counts)


# ======================= Venues =======================

@bp.route("/venues")
@admin_required
def list_venues():
    venues = get_db().execute(
        "SELECT v.id, v.name, v.capacity, v.location, COUNT(e.id) AS event_count "
        "FROM venues v "
        "LEFT JOIN events e ON e.venue_id = v.id "
        "GROUP BY v.id "
        "ORDER BY v.name"
    ).fetchall()
    return render_template("admin/venues.html", venues=venues)


@bp.route("/venues/new", methods=["GET", "POST"])
@admin_required
def create_venue():
    form = {}  # empty form the first time
    if request.method == "POST":
        values, error = read_venue_form(request.form)
        if error:
            flash(error, "error")
            form = request.form  # show what the admin typed again
        else:
            conn = get_db()
            conn.execute(
                "INSERT INTO venues (name, capacity, location) VALUES (?, ?, ?)",
                (values["name"], values["capacity"], values["location"]),
            )
            conn.commit()
            flash(f"Venue '{values['name']}' created.", "success")
            return redirect(url_for("admin.list_venues"))
    return render_template("admin/venue_form.html", form=form, venue_id=None)


@bp.route("/venues/<int:venue_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_venue(venue_id):
    conn = get_db()
    venue = conn.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()
    if venue is None:
        abort(404)

    form = dict(venue)  # fill the form with the current values
    if request.method == "POST":
        values, error = read_venue_form(request.form, venue_id=venue_id)
        if error:
            flash(error, "error")
            form = request.form
        else:
            conn.execute(
                "UPDATE venues SET name = ?, capacity = ?, location = ? WHERE id = ?",
                (values["name"], values["capacity"], values["location"], venue_id),
            )
            conn.commit()
            flash(f"Venue '{values['name']}' updated.", "success")
            return redirect(url_for("admin.list_venues"))
    return render_template("admin/venue_form.html", form=form, venue_id=venue_id)


@bp.route("/venues/<int:venue_id>/delete", methods=["POST"])
@admin_required
def delete_venue(venue_id):
    conn = get_db()
    event_count = conn.execute(
        "SELECT COUNT(*) FROM events WHERE venue_id = ?", (venue_id,)
    ).fetchone()[0]
    if event_count > 0:
        # The foreign key would block this anyway; we give a clearer message.
        flash(f"Cannot delete: {event_count} event(s) use this venue. "
              "Move or delete them first.", "error")
    else:
        conn.execute("DELETE FROM venues WHERE id = ?", (venue_id,))
        conn.commit()
        flash("Venue deleted.", "success")
    return redirect(url_for("admin.list_venues"))


# ======================= Events =======================

@bp.route("/events")
@admin_required
def list_events():
    """All events (past and upcoming) with how many students registered."""
    events = get_db().execute(
        "SELECT e.id, e.title, e.category, e.start_time, e.capacity, "
        "       v.name AS venue_name, COUNT(r.id) AS registered "
        "FROM events e "
        "JOIN venues v ON v.id = e.venue_id "
        "LEFT JOIN registrations r ON r.event_id = e.id "
        "GROUP BY e.id "
        "ORDER BY e.start_time"
    ).fetchall()
    return render_template("admin/events.html", events=events)


def all_venues():
    """Venues for the dropdown in the event form."""
    return get_db().execute(
        "SELECT id, name, capacity FROM venues ORDER BY name"
    ).fetchall()


@bp.route("/events/new", methods=["GET", "POST"])
@admin_required
def create_event():
    form = {}
    if request.method == "POST":
        values, error = read_event_form(request.form)
        if error:
            flash(error, "error")
            form = request.form
        else:
            conn = get_db()
            conn.execute(
                "INSERT INTO events (title, description, category, venue_id, "
                "start_time, end_time, capacity, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (values["title"], values["description"], values["category"],
                 values["venue_id"], values["start_time"], values["end_time"],
                 values["capacity"], current_user.id),
            )
            conn.commit()
            flash(f"Event '{values['title']}' created.", "success")
            return redirect(url_for("admin.list_events"))
    return render_template(
        "admin/event_form.html", form=form, event_id=None,
        venues=all_venues(), categories=CATEGORIES,
    )


@bp.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_event(event_id):
    conn = get_db()
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if event is None:
        abort(404)

    # datetime-local inputs need 'YYYY-MM-DDTHH:MM', so swap the space for a T.
    form = dict(event)
    form["start_time"] = event["start_time"].replace(" ", "T")
    form["end_time"] = event["end_time"].replace(" ", "T")

    if request.method == "POST":
        values, error = read_event_form(request.form, event_id=event_id)
        if error:
            flash(error, "error")
            form = request.form
        else:
            conn.execute(
                "UPDATE events SET title = ?, description = ?, category = ?, venue_id = ?, "
                "start_time = ?, end_time = ?, capacity = ? WHERE id = ?",
                (values["title"], values["description"], values["category"],
                 values["venue_id"], values["start_time"], values["end_time"],
                 values["capacity"], event_id),
            )
            conn.commit()
            flash(f"Event '{values['title']}' updated.", "success")
            return redirect(url_for("admin.list_events"))
    return render_template(
        "admin/event_form.html", form=form, event_id=event_id,
        venues=all_venues(), categories=CATEGORIES,
    )


@bp.route("/events/<int:event_id>/delete", methods=["POST"])
@admin_required
def delete_event(event_id):
    conn = get_db()
    # ON DELETE CASCADE in schema.sql removes this event's registrations too.
    cursor = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    if cursor.rowcount == 0:
        abort(404)
    flash("Event deleted.", "success")
    return redirect(url_for("admin.list_events"))


# ======================= Participants =======================

def get_event_or_404(event_id):
    event = get_db().execute(
        "SELECT id, title, start_time, capacity FROM events WHERE id = ?", (event_id,)
    ).fetchone()
    if event is None:
        abort(404)
    return event


@bp.route("/events/<int:event_id>/participants")
@admin_required
def participants(event_id):
    event = get_event_or_404(event_id)
    return render_template(
        "admin/participants.html", event=event, participants=get_participants(event_id)
    )


@bp.route("/events/<int:event_id>/participants.csv")
@admin_required
def participants_csv(event_id):
    """Download the participant list as a CSV file (opens in Excel)."""
    get_event_or_404(event_id)

    # Write the CSV into a text buffer in memory instead of a file on disk.
    buffer = io.StringIO()
    writer = csv.writer(buffer)  # handles commas and quotes inside values for us
    writer.writerow(["Name", "Email", "Registered at"])
    for p in get_participants(event_id):
        writer.writerow([p["name"], p["email"], p["registered_at"]])

    # Content-Disposition: attachment tells the browser to download, not display.
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition":
                 f"attachment; filename=event_{event_id}_participants.csv"},
    )
