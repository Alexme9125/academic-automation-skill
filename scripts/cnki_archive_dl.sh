#!/bin/zsh
# Archive one unique stable PDF; unrelated .crdownload files never block it.
# cnki_archive_dl.sh <folder> [name.pdf] [minutes=5] [--snapshot path]
set -u
[[ $# -ge 1 ]] || exit 64
DEST="$1"; NAME="${2:-}"; MIN="${3:-5}"
DIR="$(cd "$(dirname "$0")" && pwd)"
DOWNLOADS="${CNKI_DOWNLOADS_DIR:-$HOME/Downloads}"
ARGS=()
if [[ "${4:-}" == --snapshot ]]; then ARGS=(--snapshot "$5"); fi
SINCE=$(python3 -c 'import time,sys; print(time.time()-float(sys.argv[1])*60)' "$MIN") || exit 64
CAND=$(python3 "$DIR/download_watch.py" wait "$DOWNLOADS" --since "$SINCE" --timeout 30 "${ARGS[@]}") || exit $?
if [[ -n "$NAME" && "$NAME" != *.pdf && "$NAME" != *.PDF ]]; then NAME="${NAME}.pdf"; fi
DESTFILE=$(python3 "$DIR/download_watch.py" archive "$CAND" "$DEST" --name "$NAME") || exit $?
echo "OK $DESTFILE"
file "$DESTFILE"
echo "PAGES:$(python3 "$DIR/pdf_pages.py" "$DESTFILE")"
