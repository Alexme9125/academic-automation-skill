#!/bin/zsh
# 按完整 DOI 从出版社获取 OA PDF（macOS）。
# 用法: oa_dl.sh <DOI> <目标文件夹> [归档文件名不含扩展名]
# 退出码:
#   0  curl 成功并归档
#   2  DOI 未注册（doi.org 404）
#   3  已打开浏览器，需等待 ~/Downloads 或 Cmd+S（见 stdout 的 NEED_BROWSER）
#   4  curl 得到的不是 PDF / 未找到下载链接
#   64 参数错误
set -u
if [[ $# -lt 2 ]]; then
  echo '用法: oa_dl.sh <DOI> <目标文件夹> [归档文件名]' >&2
  exit 64
fi
DOI="$1"
DEST="$2"
STEM="${3:-}"
DIR="$(cd "$(dirname "$0")" && pwd)"
RUNJS="$DIR/macos_chrome_js.sh"
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
TMP="/tmp/oa_${$}.pdf"
mkdir -p "$DEST"

archive_tmp() {
  local name="$STEM"
  if [[ -z "$name" ]]; then
    name=$(python3 -c "import sys; print(sys.argv[1].replace('/','_').replace(':','_'))" "$DOI")
  fi
  [[ "$name" != *.pdf && "$name" != *.PDF ]] && name="${name}.pdf"
  mv -n "$TMP" "$DEST/$name" 2>/dev/null || mv "$TMP" "$DEST/$name"
  echo "OK $DEST/$name"
  file "$DEST/$name"
  echo "PAGES:$(python3 "$DIR/pdf_pages.py" "$DEST/$name")"
}

curl_pdf() {
  local url="$1"
  echo "CURL: $url"
  curl -sL --fail --max-time 60 -A "$UA" -o "$TMP" "$url" || return 1
  if file "$TMP" | grep -qi 'PDF'; then
    return 0
  fi
  echo "NOT_PDF: $(file "$TMP")"
  return 1
}

need_browser() {
  local kind="$1"
  local url="$2"
  echo "NEED_BROWSER $kind $url"
  echo "NEXT: 若 kind=jump，等 ~/Downloads 出现 PDF 后跑 cnki_archive_dl.sh"
  echo "NEXT: 若 kind=save-dialog，用 Computer Use：Cmd+S → 点 Save（OKButton）→ 再归档"
}

PROBE=$(curl -sI -L --max-time 30 -A "$UA" -o /tmp/oa_hdr_$$ -w '%{http_code} %{url_effective}' "https://doi.org/${DOI}" || true)
CODE="${PROBE%% *}"
FINAL="${PROBE#* }"
echo "PROBE: $CODE $FINAL"
if [[ "$CODE" == "404" || -z "$FINAL" ]]; then
  echo "DOI_UNREGISTERED $DOI"
  exit 2
fi

HOST=$(python3 -c "from urllib.parse import urlparse; import sys; print((urlparse(sys.argv[1]).hostname or '').lower())" "$FINAL" 2>/dev/null || echo '')
echo "HOST: $HOST"

case "$HOST" in
  *sagepub.com)
    open -a "Google Chrome" "$FINAL"
    sleep 3
    PDFURL="https://journals.sagepub.com/doi/pdf/${DOI}?download=true"
    python3 - "$PDFURL" /tmp/oa_jump.js "$DIR/pub/jump.js" <<'PY'
import json, sys
url, out, tmpl = sys.argv[1], sys.argv[2], sys.argv[3]
js = open(tmpl, encoding='utf-8').read().replace('__URL__', json.dumps(url))
open(out, 'w', encoding='utf-8').write(js)
PY
    echo "JUMP: $("$RUNJS" /tmp/oa_jump.js)"
    need_browser jump "$PDFURL"
    exit 3
    ;;
  *nature.com)
    ART=$(python3 -c "import re,sys; m=re.search(r'/articles/([^/?]+)', sys.argv[1]); print(m.group(1) if m else '')" "$FINAL")
    if [[ -n "$ART" ]] && curl_pdf "https://www.nature.com/articles/${ART}.pdf"; then
      archive_tmp
      exit 0
    fi
    open -a "Google Chrome" "$FINAL"
    need_browser find-link "$FINAL"
    exit 3
    ;;
  *frontiersin.org)
    if curl_pdf "https://www.frontiersin.org/articles/${DOI}/pdf"; then
      archive_tmp
      exit 0
    fi
    if curl_pdf "https://www.frontiersin.org/journals/education/articles/${DOI}/pdf"; then
      archive_tmp
      exit 0
    fi
    open -a "Google Chrome" "$FINAL"
    need_browser find-link "$FINAL"
    exit 3
    ;;
  *springer.com|*link.springer.com)
    ENC=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe='/'))" "$DOI")
    PDFURL="https://link.springer.com/content/pdf/${ENC}.pdf"
    open -a "Google Chrome" "$PDFURL"
    need_browser save-dialog "$PDFURL"
    exit 3
    ;;
  *scirp.org)
    open -a "Google Chrome" "$FINAL"
    sleep 3
    LINKS=$("$RUNJS" "$DIR/pub/scirp.js")
    echo "PDF_CANDIDATES: $LINKS"
    PDF=$(python3 -c "
import sys
for line in sys.argv[1].splitlines():
    if '@@' in line and '.pdf' in line.lower():
        print(line.split('@@',1)[1].strip()); break
" "$LINKS")
    if [[ -n "$PDF" ]] && curl_pdf "$PDF"; then
      archive_tmp
      exit 0
    fi
    need_browser find-link "$FINAL"
    exit 3
    ;;
  *scholink.org|*bryanhouse*|*jovexplorer*)
    open -a "Google Chrome" "$FINAL"
    sleep 3
    LINKS=$("$RUNJS" "$DIR/pub/scholink.js")
    echo "PDF_CANDIDATES: $LINKS"
    PDF=$(python3 -c "
import sys
best=''
for line in sys.argv[1].splitlines():
    if '@@' not in line: continue
    url=line.split('@@',1)[1].strip()
    if '/article/download/' in url.lower():
        print(url); raise SystemExit
    if '.pdf' in url.lower() and not best: best=url
if best: print(best)
" "$LINKS")
    if [[ -n "$PDF" ]] && curl_pdf "$PDF"; then
      archive_tmp
      exit 0
    fi
    if [[ -n "$PDF" ]]; then
      python3 - "$PDF" /tmp/oa_jump.js "$DIR/pub/jump.js" <<'PY'
import json, sys
url, out, tmpl = sys.argv[1], sys.argv[2], sys.argv[3]
js = open(tmpl, encoding='utf-8').read().replace('__URL__', json.dumps(url))
open(out, 'w', encoding='utf-8').write(js)
PY
      echo "JUMP: $("$RUNJS" /tmp/oa_jump.js)"
      need_browser jump "$PDF"
      exit 3
    fi
    need_browser find-link "$FINAL"
    exit 3
    ;;
  *stemmpress*|*aeph.press*|*haiyangzhiku*)
    open -a "Google Chrome" "$FINAL"
    sleep 3
    LINKS=$("$RUNJS" "$DIR/pub/uploadfile.js")
    echo "PDF_CANDIDATES: $LINKS"
    PDF=$(python3 -c "
import sys
for line in sys.argv[1].splitlines():
    if '@@' in line and '.pdf' in line.lower():
        print(line.split('@@',1)[1].strip()); break
" "$LINKS")
    if [[ -n "$PDF" ]] && curl_pdf "$PDF"; then
      archive_tmp
      exit 0
    fi
    need_browser find-link "$FINAL"
    exit 3
    ;;
esac

open -a "Google Chrome" "$FINAL"
sleep 3
LINKS=$("$RUNJS" "$DIR/pub/find_pdf.js")
echo "PDF_CANDIDATES: $LINKS"
PDF=$(python3 -c "
import re, sys
cands = []
for line in sys.argv[1].splitlines():
    if '@@' not in line:
        continue
    label, url = line.split('@@', 1)
    url = url.strip()
    low = url.lower()
    lab = label.lower()
    score = 0
    if '.pdf' in low or '/article/download/' in low or '/uploadfile/' in low:
        score = 4
    if 'pdf' in lab:
        score = max(score, 2)
    m = re.search(r'/article/view/(\d+)/(\d+)', url)
    if m:
        url = re.sub(r'/article/view/', '/article/download/', url, count=1)
        score = max(score, 3 if 'pdf' in lab else 2)
        if 'turkish' in lab or '中文' in lab:
            score -= 1
    if score:
        cands.append((score, url))
cands.sort(key=lambda x: -x[0])
if cands:
    print(cands[0][1])
" "$LINKS")
if [[ -n "$PDF" ]] && curl_pdf "$PDF"; then
  archive_tmp
  exit 0
fi
if [[ -n "$PDF" ]]; then
  python3 - "$PDF" /tmp/oa_jump.js "$DIR/pub/jump.js" <<'PY'
import json, sys
url, out, tmpl = sys.argv[1], sys.argv[2], sys.argv[3]
js = open(tmpl, encoding='utf-8').read().replace('__URL__', json.dumps(url))
open(out, 'w', encoding='utf-8').write(js)
PY
  echo "JUMP: $("$RUNJS" /tmp/oa_jump.js)"
  need_browser jump "$PDF"
  exit 3
fi
need_browser find-link "$FINAL"
exit 4
