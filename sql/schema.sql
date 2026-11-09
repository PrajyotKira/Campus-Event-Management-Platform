-- Campus Event Management Platform: database schema (SQLite)
--
-- Run by:  flask --app app init-db   (called from scripts/setup.sh)
-- WARNING: this drops and recreates every table, so all data is lost.
--
-- Dates/times are stored as TEXT in ISO format 'YYYY-MM-DD HH:MM'.
-- ISO strings sort in time order, so < and > comparisons work correctly.
--
-- No indexes yet: they will be added later as the profiling optimisation.

-- Drop child tables first, because they reference the parent tables.
DROP TABLE IF EXISTS registrations;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS venues;
DROP TABLE IF EXISTS users;

-- People who use the system. role decides what they are allowed to do.
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,          -- never store plain passwords
    role          TEXT    NOT NULL DEFAULT 'student'
                          CHECK (role IN ('admin', 'student'))
);

-- Physical places where events happen.
CREATE TABLE venues (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    location TEXT    NOT NULL
);

-- Events created by an admin and held at a venue.
CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT,
    category    TEXT    NOT NULL,
    venue_id    INTEGER NOT NULL REFERENCES venues(id),
    start_time  TEXT    NOT NULL,
    end_time    TEXT    NOT NULL,
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    created_by  INTEGER NOT NULL REFERENCES users(id),
    CHECK (end_time > start_time)             -- an event must end after it starts
);

-- Which student is registered for which event.
CREATE TABLE registrations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    event_id      INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    registered_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (user_id, event_id)                -- a student can register only once per event
);
