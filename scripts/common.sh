#!/usr/bin/env bash
# Shared helper functions for the other scripts.
# Not run directly: other scripts load it with:  source "$(dirname "$0")/common.sh"

# Folder that contains this project (the parent of scripts/).
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"

# Find a Python that really works and store its name in $PYTHON.
# We run "--version" instead of only checking that the command exists, because on
# Windows "python3" can be a fake Microsoft Store shortcut that just prints an error.
find_python() {
    if python3 --version >/dev/null 2>&1; then
        PYTHON="python3"
    elif python --version >/dev/null 2>&1; then
        PYTHON="python"
    else
        echo "ERROR: Python 3 was not found. Install it from https://www.python.org/ and try again."
        exit 1
    fi
}

# Activate the virtual environment.
# Windows creates venv/Scripts/activate, Linux/Mac create venv/bin/activate.
activate_venv() {
    if [ -f "$VENV_DIR/Scripts/activate" ]; then
        ACTIVATE="$VENV_DIR/Scripts/activate"
    elif [ -f "$VENV_DIR/bin/activate" ]; then
        ACTIVATE="$VENV_DIR/bin/activate"
    else
        echo "ERROR: virtual environment not found. Run ./scripts/setup.sh first."
        exit 1
    fi
    # The activate script may read variables that are not set, which "set -u"
    # would treat as an error, so we switch -u off just while loading it.
    set +u
    # shellcheck disable=SC1090
    source "$ACTIVATE"
    set -u
}
