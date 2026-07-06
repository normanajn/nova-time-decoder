#!/usr/bin/env bash
#
# bootstrap.sh -- set up the nova-time-decoder Python environment.
#
# Creates a virtual environment in ./venv, upgrades pip, and installs the
# package (with test extras) in editable mode. Safe to re-run: it updates an
# existing venv in place.
#
# Works on Linux, macOS and Windows (Git Bash / MSYS2). On native Windows
# without a POSIX shell, run the equivalent commands shown in docs/GETTING_STARTED.md.
#
# Usage:
#   ./bootstrap.sh            # create/update venv and install
#   PYTHON=python3.9 ./bootstrap.sh   # pick a specific interpreter

set -euo pipefail

# Resolve the directory this script lives in, so it can be run from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Choose a Python interpreter: $PYTHON override, then python3, then python.
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON=python3
    elif command -v python >/dev/null 2>&1; then
        PYTHON=python
    else
        echo "error: no python3 or python interpreter found on PATH" >&2
        exit 1
    fi
fi

echo ">> Using interpreter: $($PYTHON --version 2>&1) ($PYTHON)"

VENV_DIR="$SCRIPT_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo ">> Creating virtual environment in $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
else
    echo ">> Reusing existing virtual environment in $VENV_DIR"
fi

# The venv layout differs between POSIX and Windows.
if [ -x "$VENV_DIR/bin/python" ]; then
    VPY="$VENV_DIR/bin/python"
else
    VPY="$VENV_DIR/Scripts/python.exe"
fi

echo ">> Upgrading pip"
"$VPY" -m pip install --upgrade pip

echo ">> Installing nova-time-decoder (editable, with test extras)"
"$VPY" -m pip install -e ".[test]"

echo ""
echo ">> Done. Activate the environment with:"
if [ -x "$VENV_DIR/bin/python" ]; then
    echo "     source venv/bin/activate"
else
    echo "     source venv/Scripts/activate    # Git Bash"
    echo "     venv\\Scripts\\activate.bat       # cmd.exe"
fi
echo ">> Then run:  nova-time-convert --now"
echo ">> Run tests: python -m pytest"
