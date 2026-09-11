#!/bin/zsh
# Compatibility entry point; implementation is shared with Windows.
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/legacy.py" oa "$@"
