#!/bin/zsh
# 知网外文库检索（macOS / Chrome / osascript）
# 英文短语自动加引号，避免分词爆炸；打开检索页后点击「外文」标签（URL 参数 rlang 无效）。
# 用法:
#   cnki_foreign_search.sh "value-added assessment"
#   cnki_foreign_search.sh "value-added assessment" --rows
# 退出码: 0 正常 | 1 切库/计数失败 | 2 计数过大（分词爆炸嫌疑）| 64 参数错误
set -u
if [[ $# -lt 1 ]]; then
  echo '用法: cnki_foreign_search.sh "英文短语" [--rows]' >&2
  exit 64
fi
Q="$1"
ROWS=0
[[ "${2:-}" == "--rows" ]] && ROWS=1

DIR="$(cd "$(dirname "$0")" && pwd)"
RUNJS="$DIR/macos_chrome_js.sh"
BASE='https://kns.cnki.net/kns8s/defaultresult/index?crossids=YSTT4HG0%2CLSTPFY1C%2CEMRPGLPA%2CJUP3MUPD%2CMPMFIG1A%2CWQ0UVIAA%2CBLZOG7CK%2CPWFIRAGL%2CNLBO1Z6R%2CNN3FJMUV&korder=SU&kw='
SETKW=/tmp/cnki_set_kw.js

eval "$(python3 - "$Q" "$BASE" "$SETKW" <<'PY'
import json, re, sys, urllib.parse
q, base, out = sys.argv[1], sys.argv[2], sys.argv[3]
raw = q.strip()
if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
    quoted = raw
else:
    quoted = raw if re.fullmatch(r'[A-Za-z0-9]+', raw) else '"' + raw.replace('"', '') + '"'
url = base + urllib.parse.quote(quoted)
js = '''(function(){
  var KEYWORD = %s;
  var inp = document.getElementById('txt_search') || document.querySelector('input.search-input');
  if (!inp) return 'no #txt_search';
  var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(inp, KEYWORD);
  inp.dispatchEvent(new Event('input', {bubbles:true}));
  inp.dispatchEvent(new Event('change', {bubbles:true}));
  return 'set ' + KEYWORD;
})()''' % json.dumps(quoted, ensure_ascii=False)
open(out, 'w', encoding='utf-8').write(js)
print('QUOTED=' + json.dumps(quoted, ensure_ascii=False))
print('SURL=' + json.dumps(url))
PY
)"

echo "QUERY: $Q"
echo "QUOTED: $QUOTED"
echo "URL: $SURL"

open -a "Google Chrome" "$SURL"
sleep 2.5
SETRES=$("$RUNJS" "$SETKW")
echo "SETKW: $SETRES"
CLICK=$("$RUNJS" "$DIR/cnki_foreign.js")
echo "FOREIGN: $CLICK"
if [[ "$CLICK" == notfound* || -z "$CLICK" ]]; then
  echo "RESULT: NO_FOREIGN_TAB"
  exit 1
fi
sleep 2.5
CNT=$("$RUNJS" "$DIR/cnki_count.js")
if [[ "$CNT" != *'"n":'* ]]; then
  sleep 2
  CNT=$("$RUNJS" "$DIR/cnki_count.js")
fi
echo "COUNT: $CNT"

N=$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('n') or 0)" "$CNT" 2>/dev/null || echo 0)
if [[ "$N" -gt 50000 ]]; then
  echo "RESULT: PHRASE_TOO_BROAD n=$N  （英文短语必须带引号，例如 \"value-added assessment\"）"
  exit 2
fi
if [[ "$N" -eq 0 ]]; then
  echo "RESULT: ZERO"
  exit 1
fi
echo "RESULT: OK n=$N"
if [[ $ROWS -eq 1 ]]; then
  echo "ROWS: $("$RUNJS" "$DIR/cnki_rows.js")"
fi
