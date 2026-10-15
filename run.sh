#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${GODOT:-}" ]; then TASK_GODOT=$GODOT
elif command -v godot >/dev/null 2>&1; then TASK_GODOT=$(command -v godot)
elif [ -x "$HOME/Applications/Godot.app/Contents/MacOS/Godot" ]; then TASK_GODOT="$HOME/Applications/Godot.app/Contents/MacOS/Godot"
else TASK_GODOT=/Applications/Godot.app/Contents/MacOS/Godot
fi
if [ ! -x "$TASK_GODOT" ]; then
 echo 'FlySwarm: Godot 4 is missing. Install Godot or set GODOT to its executable.' >&2
 exit 1
fi
export FLYSWARM_ROOT="$TASK_ROOT"
export FLYSWARM_PYTHON="${PYTHON:-$TASK_ROOT/.venv/bin/python}"
if [ ! -d "$TASK_ROOT/frontend/godot/.godot/imported" ]; then
 "$TASK_GODOT" --headless --editor --path "$TASK_ROOT/frontend/godot" --import
fi
# Godot owns on-demand backend/job processes and cleans them up on exit.
exec "$TASK_GODOT" --path "$TASK_ROOT/frontend/godot" "$@"
