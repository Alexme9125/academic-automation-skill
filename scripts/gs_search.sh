#!/bin/zsh
# 谷歌学术检索（macOS / Chrome / osascript）
# 用法:
#   gs_search.sh '"value-added assessment" education' out.json
#   gs_search.sh '"value-added assessment" education' out.json --pages 2 --year 2015
set -u
if [[ $# -lt 2 ]]; then
  echo '用法: gs_search.sh "<query>" <out.json> [--pages N] [--year YYYY]' >&2
  exit 64
fi
Q="$1"
OUT="$2"
shift 2
PAGES=1
YEAR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pages) PAGES="$2"; shift 2 ;;
    --year) YEAR="$2"; shift 2 ;;
    *) echo "未知参数 $1" >&2; exit 64 ;;
  esac
done
DIR="$(cd "$(dirname "$0")" && pwd)"
RUNJS="$DIR/macos_chrome_js.sh"
ROWS_JS="$DIR/gs_rows.js"
WORKDIR=$(mktemp -d /tmp/gs_search.XXXX)

SURL=$(python3 -c "import sys,urllib.parse; q,y=sys.argv[1],sys.argv[2]; p=[('hl','en'),('as_sdt','0,5'),('q',q)]+( [('as_ylo',y)] if y else [] ); print('https://scholar.google.com/scholar?'+urllib.parse.urlencode(p))" "$Q" "$YEAR")
echo "URL: $SURL"

URL="$SURL"
i=1
while [[ $i -le $PAGES ]]; do
  open -a "Google Chrome" "$URL"
  sleep 3.2
  RAW=$("$RUNJS" "$ROWS_JS")
  echo "$RAW" > "$WORKDIR/p$i.json"
  echo "PAGE $i: $(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print('captcha' if d.get('captcha') else 'n='+str(d.get('n'))+' '+ (d.get('stats') or ''))" "$RAW")"
  python3 -c "import json,sys; d=json.loads(open(sys.argv[1],encoding='utf-8').read()); sys.exit(2 if d.get('captcha') else 0)" "$WORKDIR/p$i.json" || {
    echo "CAPTCHA: 请在 Chrome 完成人机验证后重跑"
    exit 2
  }
  if [[ $i -lt $PAGES ]]; then
    URL=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1],encoding='utf-8')).get('next') or '')" "$WORKDIR/p$i.json")
    if [[ -z "$URL" ]]; then
      echo "NO_NEXT 停在第 $i 页"
      break
    fi
  fi
  i=$((i + 1))
done

python3 - "$WORKDIR" "$OUT" "$Q" "$SURL" <<'PY'
import json, sys, os
wd, out, q, surl = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
rows, seen, stats = [], set(), ''
for name in sorted(os.listdir(wd)):
    if not name.endswith('.json'):
        continue
    d = json.load(open(os.path.join(wd, name), encoding='utf-8'))
    stats = d.get('stats') or stats
    for row in d.get('rows') or []:
        key = (row.get('title') or '').lower()
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(row)
json.dump({'query': q, 'start_url': surl, 'stats': stats, 'n': len(rows), 'rows': rows},
          open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
open(out, 'a', encoding='utf-8').write('\n')
print(f"wrote {len(rows)} records -> {out}")
PY
rm -rf "$WORKDIR"
