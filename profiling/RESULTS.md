# Profiling results: reports and event search

## Setup

| | |
|---|---|
| Data | 2000 events, 67,423 registrations, 10 venues, 100 students (`./scripts/seed.sh`, fixed random seed) |
| Tool | Python's `cProfile` + `pstats`; wall-clock with `time.perf_counter()`; SQL statements counted with `sqlite3.Connection.set_trace_callback` |
| Script | `./scripts/profile.sh <label>` → `profiling/run_profile.py` and `profiling/explain.py` |
| Timing | each workload run 3 times **without** the profiler; the table shows the average |
| Machine | Windows 11, Python 3.14, SQLite (built into Python), run 2026-11-09 |

Raw output for each run is in `profiling/before/`, `profiling/rewrite_only/` and `profiling/after/`
(`timings.txt`, `profile_stats.txt`, `query_plans.txt`, `profile.prof`).

## 1. The bottleneck (before)

The first version of `app/reports.py` fetched all events and then called
`count_registrations(event_id)` **once per event** inside a Python loop. That's
the *N+1 query problem*: 1 query for the list + N queries for the counts.

Top of `profiling/before/profile_stats.txt` (one profiled run of all workloads):

```
         86185 function calls in 10.646 seconds
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
     6000    0.020    0.000   10.540    0.002 reports.py:21(count_registrations)
     6016   10.479    0.002   10.479    0.002 {method 'execute' of 'sqlite3.Connection' objects}
        1    0.010    0.010    3.574    3.574 reports.py:28(event_stats)
        1    0.005    0.005    3.511    3.511 reports.py:75(venue_utilisation)
        1    0.008    0.008    3.496    3.496 reports.py:56(popular_categories)
        3    0.000    0.000    0.063    0.021 events.py:52(search_events)
```

**Reading it:** `count_registrations` was called 6000 times (2000 per report) and accounts for
10.54 of the 10.65 seconds (99%). Almost all of that is `tottime` inside SQLite's `execute`,
not in our Python code. So the problem is not slow Python: it is **too many queries, each
doing too much work**.

**Why each query was slow:** `EXPLAIN QUERY PLAN` for the per-event count was

```
SCAN registrations USING COVERING INDEX sqlite_autoindex_registrations_1
```

The only index on `registrations` was the automatic one from `UNIQUE(user_id, event_id)`. It
starts with `user_id`, so it is no help for `WHERE event_id = ?`, and SQLite reads **all 67,423
entries** for every single count: about 2000 × 67,423 ≈ 135 million entries per report.

## 2. The fixes

1. **Query rewrite (fix the N+1 problem).** Each report is now **one** query using
   `LEFT JOIN registrations ... GROUP BY`, so the database counts everything in one pass
   (`EVENT_STATS_SQL`, `CATEGORIES_SQL`, `VENUES_SQL` in `app/reports.py`).
2. **Indexes** in `sql/indexes.sql` (applied by `setup.sh` and `profile.sh`):
   - `idx_registrations_event` on `registrations(event_id)`: counting/joining registrations per event
   - `idx_events_venue_start` on `events(venue_id, start_time)`: venue filter and clash check
   - `idx_events_category` on `events(category)`: category filter

   An index on `registrations(user_id)` was **not** added: the UNIQUE constraint's automatic
   index already starts with `user_id`, and the query plan for `WHERE user_id = ? AND event_id = ?`
   already shows `SEARCH ... USING COVERING INDEX sqlite_autoindex_registrations_1`. A
   duplicate index would only slow down inserts.

## 3. Before / after

Average wall-clock time per call, in milliseconds (lower is better).

| Workload | SQL calls before | SQL calls after | Before (ms) | Rewrite only (ms) | Rewrite + indexes (ms) | Speed-up |
|---|---:|---:|---:|---:|---:|---:|
| `event_stats` | 2001 | 1 | 3597.5 | 22.9 | **9.1** | ~395× |
| `popular_categories` | 2001 | 1 | 3502.5 | 36.0 | **6.5** | ~539× |
| `venue_utilisation` | 2011 | 1 | 3752.9 | 19.8 | **6.0** | ~625× |
| `search_events` (3 searches) | 3 | 3 | 63.1 | 66.0 | **10.9** | ~5.8× |
| **Total** | **6016** | **6** | **10,916.1** | **144.7** | **32.6** | **~335×** |

- *Rewrite only* = new queries, no indexes (`APPLY_INDEXES=0 ./scripts/profile.sh rewrite_only`).
- One extra, ad-hoc measurement: the **old** N+1 loop of `event_stats` on the **indexed**
  database took about **115 ms**. So the indexes alone give ~31×, the rewrite alone ~157×,
  and both together ~395×. Both fixes matter, and they help each other.
- The search was always one query, so its SQL count did not change; it got faster only
  because of the index (about 63 ms → 11 ms for three searches).

cProfile after (`profiling/after/profile_stats.txt`):

```
         6139 function calls in 0.034 seconds
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        6    0.026    0.004    0.026    0.004 {method 'execute' of 'sqlite3.Connection' objects}
        3    0.000    0.000    0.011    0.004 events.py:99(search_events)
        1    0.002    0.002    0.010    0.010 reports.py:72(event_stats)
        1    0.000    0.000    0.007    0.007 reports.py:86(popular_categories)
        1    0.000    0.000    0.006    0.006 reports.py:94(venue_utilisation)
     2010    0.000    0.000    0.001    0.000 reports.py:18(percent)
```

`execute` went from **6016 calls / 10.48 s** to **6 calls / 0.026 s**. Total function calls
dropped from 86,185 to 6,139.

## 4. Query plans (EXPLAIN QUERY PLAN)

Full output: `profiling/before/query_plans.txt` and `profiling/after/query_plans.txt`.
`SCAN` = read every row; `SEARCH ... USING INDEX` = jump straight to matching rows;
`AUTOMATIC ... INDEX` = SQLite built a temporary index for this one query and threw it away.

**Event search, no filters** (the main events page)

| Before | After |
|---|---|
| `SCAN e` | `SCAN e` |
| `SEARCH v USING INTEGER PRIMARY KEY (rowid=?)` | `SEARCH v USING INTEGER PRIMARY KEY (rowid=?)` |
| `BLOOM FILTER ON r (event_id=?)` | |
| `SEARCH r USING AUTOMATIC COVERING INDEX (event_id=?) LEFT-JOIN` | `SEARCH r USING COVERING INDEX idx_registrations_event (event_id=?) LEFT-JOIN` |
| `USE TEMP B-TREE FOR ORDER BY` | `USE TEMP B-TREE FOR ORDER BY` |

Before, SQLite had to **build a temporary index on all 67k registrations on every search**,
then throw it away. After, it uses the permanent index. That is the 63 ms → 11 ms.

**Event search, category + date range**

| Before | After |
|---|---|
| `SCAN e` | `SEARCH e USING INDEX idx_events_category (category=?)` |
| `SEARCH r USING AUTOMATIC COVERING INDEX (event_id=?) LEFT-JOIN` | `SEARCH r USING COVERING INDEX idx_registrations_event (event_id=?) LEFT-JOIN` |

**Event search, venue filter**

| Before | After |
|---|---|
| `SCAN e` | `SEARCH e USING INDEX idx_events_venue_start (venue_id=? AND start_time>?)` |

**Report count per event** (the query the naive version ran ~2000 times)

| Before | After |
|---|---|
| `SCAN registrations USING COVERING INDEX sqlite_autoindex_registrations_1` | `SEARCH registrations USING COVERING INDEX idx_registrations_event (event_id=?)` |

**Venue clash check** (admin event form)

| Before | After |
|---|---|
| `SCAN events` | `SEARCH events USING INDEX idx_events_venue_start (venue_id=? AND start_time<?)` |

## 5. Why it got faster (short version)

1. **Fewer round trips.** Every `execute()` has a fixed cost (Python → SQLite, preparing the
   statement, building result objects). 6016 calls became 6.
2. **Less data read per query.** Without an index on `registrations.event_id`, each count read
   all ~67k registrations. With the index, SQLite jumps straight to the few dozen rows of one
   event. Index lookups take *O(log n)* steps instead of *O(n)*.
3. **No throw-away work.** Before, SQLite kept building an `AUTOMATIC` index for each JOIN query
   and discarding it. Now the index is built once and kept up to date.
4. **"Covering" index.** `idx_registrations_event` contains everything the count needs
   (`event_id` plus the row id), so SQLite never reads the registrations table itself.

## 6. What did not change (limits)

- **Keyword search** still shows `SCAN e`: `LIKE '%workshop%'` starts with a wildcard, so a
  normal B-tree index can't be used (it's like looking up words *containing* "shop" in a
  dictionary). Fixing that would need SQLite's full-text search (FTS5), which is out of scope.
- **Upcoming events with no filters** still scan `events`, because `start_time >= now` has no
  index of its own (the composite index starts with `venue_id`). With 2000 events that scan
  is cheap; the expensive part was the registrations join, which is now indexed.
- `venue_utilisation` still shows one `AUTOMATIC COVERING INDEX`. That one is built on the
  inner query's temporary result (2000 rows), which can't have a permanent index. It costs
  under a few ms.
- **Cost of indexes:** every INSERT/DELETE on `registrations` and `events` must also update
  the indexes, and the database file gets a little bigger. For this app, reads (browsing,
  reports) happen far more often than writes, so the trade-off is worth it.
- Tests (`tests/test_reports.py`) check the exact report numbers, so they passed unchanged
  before and after the rewrite, plus a test that adding indexes doesn't change any result.

## How to reproduce

```bash
./scripts/profile.sh after                          # rewrite + indexes
APPLY_INDEXES=0 ./scripts/profile.sh rewrite_only   # rewrite, no indexes
snakeviz profiling/after/profile.prof               # visual view (venv active)
```
The `before` numbers come from the naive `app/reports.py` in the git history
(commit "feat: add admin reports page (naive N+1 version)").
