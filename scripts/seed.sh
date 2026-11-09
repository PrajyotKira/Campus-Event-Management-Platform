#!/usr/bin/env bash
# Fill the database with fake venues, students, events and registrations.
# Admin accounts are kept; everything else is replaced.
#
# Usage:  ./scripts/seed.sh        (50 events)
#         ./scripts/seed.sh 200    (200 events)
set -euo pipefail

source "$(dirname "$0")/common.sh"
cd "$PROJECT_ROOT"

# $1 is the first argument; if it is missing, use 50.
NUM_EVENTS="${1:-50}"

# Accept only a whole number greater than 0 (=~ checks against a regular expression).
if ! [[ "$NUM_EVENTS" =~ ^[0-9]+$ ]] || [ "$NUM_EVENTS" -eq 0 ]; then
    echo "ERROR: number of events must be a positive whole number, got '$NUM_EVENTS'."
    echo "Usage: ./scripts/seed.sh [number_of_events]"
    exit 1
fi

activate_venv

if [ ! -f "instance/campus.db" ]; then
    echo "ERROR: database not found. Run ./scripts/setup.sh first."
    exit 1
fi

echo "==> Seeding the database with $NUM_EVENTS events..."
python -m flask --app app seed --events "$NUM_EVENTS"
echo "Done. Start the app with: ./scripts/run.sh"
