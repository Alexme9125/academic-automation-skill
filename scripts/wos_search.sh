#!/bin/zsh
# Web of Science Core Collection 检索（macOS / Chrome / osascript）
# 走 Document Search（basic-search）。不要用 Smart Search：提交后可能跳到 Clarivate 个人登录。
# 用法:
#   wos_search.sh '"value-added assessment"' out.json
#   wos_search.sh '"value-added assessment"' out.json --pages 2 --oa
# 退出码: 0 正常 | 1 无结果/未进入结果页 | 2 登录墙或人机验证 | 64 参数错误
set -u
if [[ $# -lt 2 ]]; then
  echo '用法: wos_search.sh "<query>" <out.json> [--pages N] [--oa]' >&2
  exit 64
fi
Q="$1"
OUT="$2"
shift 2
PAGES=1
OA=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pages) PAGES="$2"; shift 2 ;;
    --oa) OA=1; shift ;;
    *) echo "未知参数 $1" >&2; exit 64 ;;
  esac
done
DIR="$(cd "$(dirname "$0")" && pwd)"
RUNJS="$DIR/macos_chrome_js.sh"
WORKDIR=$(mktemp -d /tmp/wos_search.XXXX)
SUBMIT="$WORKDIR/submit.js"

eval "$(python3 - "$Q" "$SUBMIT" <<'PY'
import json, re, sys
q, out = sys.argv[1], sys.argv[2]
raw = q.strip()
if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
    quoted = raw
else:
    quoted = raw if re.fullmatch(r'[A-Za-z0-9]+', raw) else '"' + raw.replace('"', '') + '"'
js = r'''(function(){
  var KEYWORD = %s;
  var el = document.getElementById('search-option-0');
  if (!el) return JSON.stringify({ok:false, err:'no #search-option-0'});
  el.focus();
  var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(el, KEYWORD);
  el.dispatchEvent(new Event('input', {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
  var btn = null;
  document.querySelectorAll('button').forEach(function(b){
    var t = (b.textContent || '').replace(/\s+/g, ' ').trim();
    if (/search Search/i.test(t) || t === 'Search') btn = b;
  });
  if (!btn) return JSON.stringify({ok:false, err:'no Search button', value:el.value});
  if (btn.disabled) {
    btn.disabled = false;
    btn.removeAttribute('disabled');
  }
  btn.click();
  return JSON.stringify({ok:true, value:el.value});
})()''' % json.dumps(quoted, ensure_ascii=False)
open(out, 'w', encoding='utf-8').write(js)
print('QUOTED=' + json.dumps(quoted, ensure_ascii=False))
PY
)"

echo "QUERY: $Q"
echo "QUOTED: $QUOTED"
SURL='https://www.webofscience.com/wos/woscc/basic-search'
echo "URL: $SURL"
open -a "Google Chrome" "$SURL"
sleep 4.5

ST=$("$RUNJS" "$DIR/wos_status.js")
echo "STATUS: $ST"
python3 -c "import json,sys; d=json.loads(sys.argv[1]); sys.exit(2 if d.get('login') or d.get('captcha') else 0)" "$ST" || {
  echo "LOGIN_OR_CAPTCHA: 请在 Chrome 完成机构登录或人机验证后重跑（不要用 Smart Search）"
  rm -rf "$WORKDIR"
  exit 2
}

"$RUNJS" "$DIR/wos_dismiss.js" >/dev/null || true
SUB=$("$RUNJS" "$SUBMIT")
echo "SUBMIT: $SUB"

ok=0
for i in {1..18}; do
  U=$(osascript -e 'tell application "Google Chrome" to get URL of active tab of front window' 2>/dev/null || echo '')
  T=$(osascript -e 'tell application "Google Chrome" to get title of active tab of front window' 2>/dev/null || echo '')
  case "$U" in
    *access.clarivate.com/login*)
      echo "LOGIN: $U"
      rm -rf "$WORKDIR"
      exit 2
      ;;
    */summary/*)
      echo "SUMMARY: $T"
      echo "SUMMARY_URL: $U"
      ok=1
      break
      ;;
  esac
  sleep 1
done
if [[ $ok -ne 1 ]]; then
  echo "RESULT: NO_SUMMARY 仍停在检索页或未知页"
  rm -rf "$WORKDIR"
  exit 1
fi

if [[ $OA -eq 1 ]]; then
  echo "OA_FILTER: $("$RUNJS" "$DIR/wos_oa.js")"
  sleep 5
  echo "OA_STATUS: $("$RUNJS" "$DIR/wos_status.js")"
fi

i=1
while [[ $i -le $PAGES ]]; do
  for s in 1 2 3 4 5 6; do
    "$RUNJS" "$DIR/wos_scroll.js" >/dev/null || true
    sleep 0.9
  done
  RAW=$("$RUNJS" "$DIR/wos_rows.js")
  echo "$RAW" > "$WORKDIR/p$i.json"
  echo "PAGE $i: $(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print('login' if d.get('login') else 'captcha' if d.get('captcha') else 'n='+str(d.get('n'))+' stats='+str(d.get('stats') or '')+' next='+str(d.get('next')))" "$RAW")"
  python3 -c "import json,sys; d=json.loads(sys.argv[1]); sys.exit(2 if d.get('login') or d.get('captcha') else 0)" "$RAW" || {
    echo "LOGIN_OR_CAPTCHA: 请在 Chrome 完成后重跑"
    rm -rf "$WORKDIR"
    exit 2
  }
  if [[ $i -lt $PAGES ]]; then
    HASNEXT=$(python3 -c "import json,sys; print('1' if json.loads(sys.argv[1]).get('next') else '')" "$RAW")
    if [[ -z "$HASNEXT" ]]; then
      echo "NO_NEXT 停在第 $i 页"
      break
    fi
    echo "NEXT: $("$RUNJS" "$DIR/wos_next.js")"
    sleep 4
  fi
  i=$((i + 1))
done

python3 - "$WORKDIR" "$OUT" "$Q" "$QUOTED" "$SURL" <<'PY'
import json, sys, os
wd, out, q, quoted, surl = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
rows, seen, stats, start = [], set(), '', ''
for name in sorted(os.listdir(wd)):
    if not name.endswith('.json'):
        continue
    d = json.load(open(os.path.join(wd, name), encoding='utf-8'))
    stats = d.get('stats') or stats
    start = start or d.get('url') or ''
    for row in d.get('rows') or []:
        key = (row.get('ut') or row.get('href') or row.get('title') or '').lower()
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(row)
json.dump({
    'query': q,
    'quoted': quoted,
    'start_url': surl,
    'summary_url': start,
    'stats': stats,
    'n': len(rows),
    'rows': rows
}, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
open(out, 'a', encoding='utf-8').write('\n')
print(f"wrote {len(rows)} records -> {out}")
PY
rm -rf "$WORKDIR"
if [[ ! -s "$OUT" ]]; then
  echo "RESULT: ZERO"
  exit 1
fi
N=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1],encoding='utf-8')).get('n') or 0)" "$OUT")
if [[ "$N" -eq 0 ]]; then
  echo "RESULT: ZERO"
  exit 1
fi
echo "RESULT: OK n=$N"
