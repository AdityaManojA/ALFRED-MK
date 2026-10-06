#!/bin/bash
# ==============================================================================
# ALFRED Mark-V: Native macOS One-Click Launcher
# Double-click this script from Finder or execute from terminal.
# ==============================================================================

set -e

# Change directory to the repository root
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "============================================================"
echo "🦇 ALFRED Mark-V — macOS Optimized Launch"
echo "============================================================"

# Hardware & Apple Silicon Optimization Flags
export PYTHONUNBUFFERED=1
export KMP_BLOCKTIME=0
export OMP_WAIT_POLICY=PASSIVE
export OMP_NUM_THREADS=4
export VECLIB_MAXIMUM_THREADS=4

# Check for virtual environment
if [ -d "$DIR/venv" ]; then
    PYTHON_EXEC="$DIR/venv/bin/python"
elif [ -d "$DIR/.venv" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python"
else
    PYTHON_EXEC="$(which python3)"
fi

echo "• Python:   $PYTHON_EXEC"
echo "• Platform: $(uname -m) macOS $(sw_vers -productVersion)"

# Launch ALFRED
exec "$PYTHON_EXEC" main.py "$@"
