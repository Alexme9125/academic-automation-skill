#!/bin/zsh
# 把 ~/Downloads 里最近几分钟出现的 PDF（排除 ._*）归档到目标文件夹。
# 用法: cnki_archive_dl.sh <目标文件夹> [新文件名.pdf] [查找窗口分钟=5]
set -u
if [[ $# -lt 1 ]]; then
  echo '用法: cnki_archive_dl.sh <目标文件夹> [新文件名.pdf] [分钟]' >&2
  exit 64
fi
DEST="$1"
NAME="${2:-}"
MIN="${3:-5}"
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DEST"
CAND=""
for i in {1..15}; do
  if find "$HOME/Downloads" -maxdepth 1 \( -name '*.crdownload' -o -name 'Unconfirmed *' \) -mmin -"$MIN" 2>/dev/null | grep -q .; then
    sleep 2
    continue
  fi
  CAND=$(find "$HOME/Downloads" -maxdepth 1 -iname '*.pdf' ! -name '._*' -mmin -"$MIN" -print0 2>/dev/null \
    | xargs -0 ls -t 2>/dev/null | head -1)
  [[ -n "$CAND" ]] && break
  sleep 2
done
if [[ -z "$CAND" ]]; then
  echo "NOTFOUND"
  ls -lt "$HOME/Downloads" | head -5
  exit 4
fi
BASE=$(basename "$CAND")
if [[ -n "$NAME" ]]; then
  [[ "$NAME" != *.pdf && "$NAME" != *.PDF ]] && NAME="${NAME}.pdf"
  BASE="$NAME"
fi
# exFAT 上 mv 可能报 set owner/group Operation not permitted，文件通常已到位
mv -n "$CAND" "$DEST/$BASE" 2>/dev/null || mv "$CAND" "$DEST/$BASE"
echo "OK $DEST/$BASE"
file "$DEST/$BASE"
echo "PAGES:$(python3 "$DIR/pdf_pages.py" "$DEST/$BASE")"
