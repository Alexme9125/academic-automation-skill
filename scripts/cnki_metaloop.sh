#!/bin/zsh
# urls.txt out.json [custom-meta.js] [--refresh]; progress lives next to out.json.
DIR="$(cd "$(dirname "$0")" && pwd)"
[[ $# -ge 2 ]] || exit 64
IN="$1"; OUT="$2"; shift 2
ARGS=()
if [[ $# -gt 0 && "$1" != --* ]]; then ARGS=(--meta-script "$1"); shift; fi
exec python3 "$DIR/search_resume.py" meta "$IN" "$OUT" "${ARGS[@]}" "$@"
