#!/bin/zsh
# 批量打开知网详情页，提取题录 JSON（含完整 DOI）。
# 用法: cnki_metaloop.sh <urls.txt> <out.json>
# urls.txt 每行一个 kcms2/article/abstract 链接。
set -u
if [[ $# -lt 2 ]]; then
  echo '用法: cnki_metaloop.sh <urls.txt> <out.json>' >&2
  exit 64
fi
IN="$1"
OUT="$2"
DIR="$(cd "$(dirname "$0")" && pwd)"
RUNJS="$DIR/macos_chrome_js.sh"
META_JS="${3:-$DIR/cnki_meta.js}"
TMP=/tmp/cnki_metaloop_items.jsonl
: > "$TMP"

while IFS= read -r url || [[ -n "${url:-}" ]]; do
  url="${url%%$'\r'}"
  [[ -z "$url" || "$url" == \#* ]] && continue
  open -a "Google Chrome" "$url"
  sleep 3.5
  META=$("$RUNJS" "$META_JS")
  python3 - "$META" "$url" >> "$TMP" <<'PY'
import json, sys
raw, url = sys.argv[1], sys.argv[2]
try:
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        obj = {"raw": raw, "parse_error": True}
except Exception:
    obj = {"raw": raw, "parse_error": True}
obj["url"] = url
print(json.dumps(obj, ensure_ascii=False))
PY
  echo "META: $url"
done < "$IN"

python3 - "$TMP" "$OUT" <<'PY'
import json, sys
items = []
with open(sys.argv[1], encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            items.append(json.loads(line))
with open(sys.argv[2], 'w', encoding='utf-8') as f:
    json.dump(items, f, ensure_ascii=False, indent=2)
    f.write('\n')
print('wrote', len(items), 'records ->', sys.argv[2])
PY
