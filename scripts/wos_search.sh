#!/bin/zsh
# Resumable search: query out.json [--pages N] [--refresh] [--oa]
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/search_resume.py" wos "$@"
