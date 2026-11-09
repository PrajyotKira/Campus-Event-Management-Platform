-- Indexes: the performance optimisation found by profiling (see profiling/RESULTS.md).
--
-- An index is a sorted copy of one or more columns with pointers back to the
-- rows, like the index at the back of a book. With it, SQLite can jump straight
-- to the matching rows instead of reading the whole table (a "full table scan").
-- The cost: a little extra disk space, and INSERT/UPDATE/DELETE must also update
-- the index. That's a good trade here because we read far more often than we write.
--
-- Run by:  flask --app app add-indexes   (called from setup.sh and profile.sh)
-- IF NOT EXISTS makes it safe to run more than once.

-- Counting/joining registrations per event (reports, seats left on every event page).
-- Without it, every COUNT(*) WHERE event_id = ? reads all registrations.
CREATE INDEX IF NOT EXISTS idx_registrations_event
    ON registrations (event_id);

-- Venue filter on the search page and the venue clash check
-- (WHERE venue_id = ? AND start_time < ? ...). The leftmost column (venue_id)
-- finds the venue, then start_time is already sorted inside it.
CREATE INDEX IF NOT EXISTS idx_events_venue_start
    ON events (venue_id, start_time);

-- Category dropdown on the search page (WHERE category = ?).
CREATE INDEX IF NOT EXISTS idx_events_category
    ON events (category);

-- Not added: an index on registrations (user_id).
-- The UNIQUE (user_id, event_id) constraint in schema.sql already makes SQLite
-- build an automatic index on (user_id, event_id). Its leftmost column is
-- user_id, so "WHERE user_id = ?" already uses it (see the query plans in
-- profiling/after/query_plans.txt). A second index would only slow down writes.
