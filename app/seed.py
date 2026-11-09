"""Fill the database with realistic fake data for demos, testing and profiling.

Run with:  flask --app app seed --events 50     (or ./scripts/seed.sh 50)

It deletes all venues, events, registrations and student accounts, then creates
new ones. Admin accounts are never deleted.
Random seeds are fixed, so the same command always produces the same data
(useful for fair before/after profiling).
"""
import random
from datetime import datetime, timedelta

import click
from faker import Faker
from werkzeug.security import generate_password_hash

from .db import get_db
from .events import CATEGORIES

# (name, capacity, location)
VENUES = [
    ("Main Auditorium", 500, "Admin Block, Ground Floor"),
    ("Seminar Hall A", 150, "Academic Block 1, First Floor"),
    ("Seminar Hall B", 120, "Academic Block 1, Second Floor"),
    ("Lecture Hall 101", 100, "Academic Block 2, Ground Floor"),
    ("Lecture Hall 202", 80, "Academic Block 2, Second Floor"),
    ("Computer Lab 3", 60, "CSE Building, Third Floor"),
    ("Open Air Theatre", 400, "Near Central Lawn"),
    ("Sports Complex", 300, "North Campus"),
    ("Football Ground", 250, "North Campus"),
    ("Library Conference Room", 40, "Central Library, First Floor"),
]

# Title ideas for each category; Faker adds a catchy subtitle.
TITLES = {
    "Technical": ["Hackathon", "Coding Contest", "Tech Talk", "Robotics Demo", "App Dev Meetup"],
    "Cultural": ["Music Night", "Dance Showcase", "Drama Performance", "Art Exhibition", "Poetry Slam"],
    "Sports": ["Football Match", "Cricket Tournament", "Badminton Open", "Basketball League", "Athletics Meet"],
    "Workshop": ["Python Workshop", "Git and GitHub Workshop", "Machine Learning Bootcamp",
                 "Web Design Workshop", "Photography Workshop"],
    "Seminar": ["Career Guidance Seminar", "Research Seminar", "Startup Seminar",
                "Guest Lecture", "Alumni Talk"],
}

STUDENT_PASSWORD = "student123"
TIME_FORMAT = "%Y-%m-%d %H:%M"


def overlaps(start, end, booked_slots):
    """True if [start, end) overlaps any (start, end) pair in booked_slots.

    Two time ranges overlap when each one starts before the other ends.
    """
    for booked_start, booked_end in booked_slots:
        if start < booked_end and end > booked_start:
            return True
    return False


@click.command("seed")
@click.option("--events", "num_events", default=50, show_default=True,
              help="Number of events to create")
@click.option("--students", "num_students", default=100, show_default=True,
              help="Number of student accounts to create")
def seed_command(num_events, num_students):
    random.seed(42)
    Faker.seed(42)
    fake = Faker("en_IN")
    conn = get_db()

    # Events need an organiser, so an admin must already exist (made by setup.sh).
    admin = conn.execute(
        "SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1"
    ).fetchone()
    if admin is None:
        raise click.ClickException("No admin account found. Run ./scripts/setup.sh first.")

    # 1. Remove old data. Children first because of the foreign keys. Admins are kept.
    conn.execute("DELETE FROM registrations")
    conn.execute("DELETE FROM events")
    conn.execute("DELETE FROM venues")
    conn.execute("DELETE FROM users WHERE role = 'student'")
    # AUTOINCREMENT remembers the last id in the sqlite_sequence table; clearing it
    # makes venue/event/registration ids start at 1 again after every seed.
    conn.execute(
        "DELETE FROM sqlite_sequence WHERE name IN ('venues', 'events', 'registrations')"
    )

    # 2. Venues
    conn.executemany(
        "INSERT INTO venues (name, capacity, location) VALUES (?, ?, ?)", VENUES
    )
    venues = conn.execute("SELECT id, capacity FROM venues").fetchall()

    # 3. Students. Hashing is deliberately slow, so we hash the shared demo
    # password once and reuse it instead of hashing it 100 times.
    password_hash = generate_password_hash(STUDENT_PASSWORD)
    students = [
        (fake.name(), f"student{i}@campus.local", password_hash)
        for i in range(1, num_students + 1)
    ]
    conn.executemany(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'student')",
        students,
    )
    student_ids = [
        row["id"] for row in conn.execute("SELECT id FROM users WHERE role = 'student'")
    ]

    # 4. Events: random times over the next 60 days, never clashing at a venue.
    booked = {venue["id"]: [] for venue in venues}  # venue id -> list of (start, end)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    created_events = []  # (event_id, capacity)
    attempts = 0
    # Give up after many tries in case there is no free slot left (very large N).
    while len(created_events) < num_events and attempts < num_events * 20:
        attempts += 1
        venue = random.choice(venues)
        start = today + timedelta(days=random.randint(1, 60), hours=random.randint(9, 18))
        end = start + timedelta(hours=random.randint(1, 3))
        if overlaps(start, end, booked[venue["id"]]):
            continue  # this slot is taken, try again
        booked[venue["id"]].append((start, end))

        category = random.choice(CATEGORIES)
        title = f"{random.choice(TITLES[category])}: {fake.catch_phrase()}"
        capacity = random.randint(20, venue["capacity"])  # never more than the venue holds
        cursor = conn.execute(
            "INSERT INTO events (title, description, category, venue_id, "
            "start_time, end_time, capacity, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (title, fake.paragraph(nb_sentences=4), category, venue["id"],
             start.strftime(TIME_FORMAT), end.strftime(TIME_FORMAT),
             capacity, admin["id"]),
        )
        created_events.append((cursor.lastrowid, capacity))

    # 5. Registrations: for each event pick a random number of different students,
    # at most the event's capacity, so no event is ever over-booked.
    # random.sample never picks the same student twice, matching UNIQUE(user_id, event_id).
    registrations = []
    for event_id, capacity in created_events:
        how_many = random.randint(0, min(capacity, len(student_ids)))
        for user_id in random.sample(student_ids, how_many):
            # Registered at some point in the last 14 days.
            registered_at = datetime.now() - timedelta(minutes=random.randint(0, 14 * 24 * 60))
            registrations.append(
                (user_id, event_id, registered_at.strftime("%Y-%m-%d %H:%M:%S"))
            )
    conn.executemany(
        "INSERT INTO registrations (user_id, event_id, registered_at) VALUES (?, ?, ?)",
        registrations,
    )

    conn.commit()

    click.echo(f"    {len(VENUES)} venues, {len(student_ids)} students, "
               f"{len(created_events)} events, {len(registrations)} registrations created.")
    if len(created_events) < num_events:
        click.echo(f"    Note: only {len(created_events)} of {num_events} events fit "
                   "without venue clashes in the next 60 days.")
    click.echo(f"    Student logins: student1@campus.local ... student{num_students}"
               f"@campus.local, password: {STUDENT_PASSWORD}")
