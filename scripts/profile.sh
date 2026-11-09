#!/usr/bin/env bash
# Profile the reports and event search on a large seeded database.
#
# Usage:  ./scripts/profile.sh <label> [events]
#         ./scripts/profile.sh before          (2000 events, results in profiling/before/)
#         ./scripts/profile.sh after 2000      (results in profiling/after/)
#         RUNS=5 ./scripts/profile.sh after    (time each workload 5 times instead of 3)
#         APPLY_INDEXES=0 ./scripts/profile.sh no_indexes   (skip sql/indexes.sql)
#
# Uses its own database file (profiling/profile.db), so your normal data in
# instance/campus.db is never touched.
set -euo pipefail

source "$(dirname "$0")/common.sh"
cd "$PROJECT_ROOT"

LABEL="${1:-}"
NUM_EVENTS="${2:-2000}"
RUNS="${RUNS:-3}"
APPLY_INDEXES="${APPLY_INDEXES:-1}"   # 1 = add the indexes, 0 = measure without them

# The label becomes a folder name, so allow only letters, digits, - and _.
if ! [[ "$LABEL" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "ERROR: please give a label such as 'before' or 'after'."
    echo "Usage: ./scripts/profile.sh <label> [number_of_events]"
    exit 1
fi
if ! [[ "$NUM_EVENTS" =~ ^[0-9]+$ ]] || [ "$NUM_EVENTS" -eq 0 ]; then
    echo "ERROR: number of events must be a positive whole number, got '$NUM_EVENTS'."
    exit 1
fi

activate_venv

# Every flask command below (and the Python profiler) uses this database.
# A relative path is fine because we cd'd to the project root above.
export CAMPUS_DB="profiling/profile.db"

echo "==> [1/5] Creating a fresh profiling database ($CAMPUS_DB)..."
python -m flask --app app init-db
python -m flask --app app create-admin

echo "==> [2/5] Seeding $NUM_EVENTS events..."
python -m flask --app app seed --events "$NUM_EVENTS"

if [ "$APPLY_INDEXES" = "1" ]; then
    echo "==> [3/5] Adding indexes (sql/indexes.sql)..."
    python -m flask --app app add-indexes
else
    echo "==> [3/5] Skipping indexes (APPLY_INDEXES=0)."
fi

echo "==> [4/5] Profiling (label: $LABEL, $RUNS timed runs each; this can take a minute)..."
# "python -m" runs profiling/run_profile.py as a module from the project root,
# so it can "import app".
python -m profiling.run_profile "$LABEL" "$RUNS"

echo "==> [5/5] Saving query plans (EXPLAIN QUERY PLAN)..."
python -m profiling.explain "$LABEL" > /dev/null
echo "    Saved in profiling/$LABEL/query_plans.txt"
