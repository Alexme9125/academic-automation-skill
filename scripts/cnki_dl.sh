#!/bin/zsh
# CNKI 单篇下载：题名(TI)/专业检索 -> 精确题名优先匹配+作者行校验 -> 详情页 -> PDF/CAJ -> 归档
# 用法: cnki_dl.sh [--expert "SU='学习进阶' AND SU='化学'"] [--affiliation "机构"] [--pages N] "检索题名" "第一作者" "目标文件夹"
#   --expert       走专业检索(/kns8s/AdvSearch?type=expert)，表达式用知网内部语法(SU/TI/AU/AF + AND/OR/NOT)；
#                  题名仍用于结果页匹配。适合 AND 多主题、同名作者加 AF='机构' 收窄。
#   --affiliation  机构过滤，拼进专业检索：已有 --expert 则追加 AND AF='…'；
#                  否则 TI='题名' AND AU='第一作者' AND AF='…'
#   --pages        NOMATCH 时自动翻页匹配的页数上限（默认 3；0 = 不翻页）
# 匹配规则：优先归一化精确匹配；包含匹配仅当「有作者且本页唯一」才采纳。短题名（≤6 字）必须给作者。
# 页面跳转一律在同一个 tab 内 set URL（macos_chrome_nav.sh）。
# 退出码: 0 成功 | 1 无结果/未匹配/空库 | 2 验证码(需人工) | 3 无下载链接 | 4 文件未落盘 | 5 收费页/无机构权限 | 64 参数错误
set -u
EXPERT=""
AFF=""
PAGES=3
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --expert) EXPERT="$2"; shift 2 ;;
    --affiliation) AFF="$2"; shift 2 ;;
    --pages) PAGES="$2"; shift 2 ;;
    *) echo "未知参数 $1" >&2; exit 64 ;;
  esac
done
if [ $# -lt 3 ]; then
  echo "用法: cnki_dl.sh [--expert \"SU='A' AND SU='B'\"] [--affiliation \"机构\"] [--pages N] \"检索题名\" \"第一作者\" \"目标文件夹\""
  exit 64
fi
if ! [[ "$PAGES" =~ ^[0-9]+$ ]]; then
  echo "无效 --pages $PAGES" >&2
  exit 64
fi
T="$1"; A="$2"; F="$3"
DIR="$(cd "$(dirname "$0")" && pwd)"
NAV="$DIR/macos_chrome_nav.sh"
GEN=/tmp/cnki_search_gen.js
EXPERTGEN=/tmp/cnki_expert_gen.js
BASE='https://kns.cnki.net/kns8s/defaultresult/index?crossids=YSTT4HG0%2CLSTPFY1C%2CEMRPGLPA%2CJUP3MUPD%2CMPMFIG1A%2CWQ0UVIAA%2CBLZOG7CK%2CPWFIRAGL%2CNLBO1Z6R%2CNN3FJMUV&korder=TI&kw='
EXPERTURL='https://kns.cnki.net/kns8s/AdvSearch?type=expert'

runjs_file() {
  osascript -e "set js to do shell script \"cat '$1'\"" \
            -e 'tell application "Google Chrome" to execute active tab of front window javascript js' 2>&1
}

page_kind() {
  runjs_file "$DIR/cnki_page.js"
}

# 题名：精确优先；包含匹配仅当有作者且本页唯一。避免短题名/子串取首条下错文。
gen_js() {
python3 - "$1" "$2" "$GEN" <<'PY'
import sys, json
t, a, out = sys.argv[1], sys.argv[2], sys.argv[3]
js = '''(function(){
  var EXPECT=__JSON__;
  var AUTHOR=__AUTHOR__;
  var norm=function(s){return (s||'').replace(/[\\s:：，,。.、；;！!？?《》〈〉()（）\\-—·“”‘’"']/g,'');};
  var t=document.body?document.body.innerText:'';
  var caps=Array.prototype.filter.call(document.querySelectorAll('*'),function(e){
    if(!e.textContent)return false;
    var s=e.textContent.trim();
    if(s!=='拖动下方拼图完成验证'&&s.indexOf('请依次点击')!==0)return false;
    var r=e.getBoundingClientRect();return r.width>0&&r.top>=0&&r.top<2000;});
  if(caps.length||/拼图校验/.test(document.title||''))return 'captcha';
  if(t.indexOf('暂无数据')>-1 && t.indexOf('请稍后')>-1)return 'empty';
  var m=t.match(/共找到\\s*(\\d+)\\s*条/);
  var c=m?m[1]:'?';
  var l=Array.prototype.filter.call(document.querySelectorAll('a[href*="kcms2/article/abstract"]'),function(a){return a.href.indexOf('anchor=')<0;});
  var nE=norm(EXPECT);
  var exact=[], contains=[], am=false;
  for(var i=0;i<l.length;i++){
    var tx=norm(l[i].textContent);
    if(!tx)continue;
    var hit=(tx===nE)||(nE.length>=4&&tx.indexOf(nE)>-1);
    if(!hit)continue;
    var tr=l[i].closest('tr');
    var rt=tr?tr.innerText.replace(/\\n+/g,' '):'';
    if(AUTHOR && rt.indexOf(AUTHOR)<0){am=true;continue;}
    var item={a:l[i],row:rt.slice(0,110)};
    if(tx===nE)exact.push(item);
    else contains.push(item);
  }
  var pick=null,row='';
  if(exact.length===1){pick=exact[0].a;row=exact[0].row;}
  else if(exact.length>1){
    return c+'@@NOMATCH@@'+exact[0].row+(am?'@@AM':'')+'@@MULTI';
  }else if(contains.length===1 && AUTHOR){
    pick=contains[0].a;row=contains[0].row;
  }else if(contains.length>1){
    return c+'@@NOMATCH@@'+contains[0].row+(am?'@@AM':'')+'@@MULTI';
  }
  if(pick){location.href=pick.href;return c+'@@MATCH@@'+row;}
  var ref=l[0];
  var rrow=ref&&ref.closest('tr');
  var r0=rrow?rrow.innerText.replace(/\\n+/g,' ').slice(0,110):'';
  return c+'@@NOMATCH@@'+r0+(am?'@@AM':'');
})()'''
open(out, 'w', encoding='utf-8').write(
    js.replace('__JSON__', json.dumps(t, ensure_ascii=False))
      .replace('__AUTHOR__', json.dumps(a, ensure_ascii=False)))
PY
}

# 专业检索：注入 textarea 并 dispatch input/change（高级检索 UI 多行按钮点不动）
gen_expert_js() {
python3 - "$1" "$EXPERTGEN" <<'PY'
import sys, json
expr, out = sys.argv[1], sys.argv[2]
js = '''(function(){
  var ta=document.querySelector('textarea.textarea-major');
  if(!ta)return 'notarea';
  var setter=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value');
  if(setter&&setter.set)setter.set.call(ta,__EXPR__);
  else ta.value=__EXPR__;
  ta.dispatchEvent(new Event('input',{bubbles:true}));
  ta.dispatchEvent(new Event('change',{bubbles:true}));
  var btn=document.querySelector('input.btn-search');
  if(!btn)return 'nobtn';
  btn.click();
  return 'searched';
})()'''
open(out, 'w', encoding='utf-8').write(js.replace('__EXPR__', json.dumps(expr, ensure_ascii=False)))
PY
}

NCH=$(python3 -c "import sys;print(sum(1 for ch in sys.argv[1] if ch.isalnum()))" "$T")
if (( NCH > 0 && NCH <= 6 )) && [[ -z "$A" ]]; then
  echo "RESULT[$T]: NEED_AUTHOR 短题名(${NCH}字)必须给第一作者，拒绝按包含匹配取首条"
  exit 64
fi
if [[ -n "$A" && -z "$EXPERT" && -z "$AFF" ]]; then
  ANCH=$(python3 -c "import sys;print(sum(1 for ch in sys.argv[1] if ch.isalnum()))" "$A")
  if (( ANCH > 0 && ANCH <= 2 )); then
    echo "WARN: 短姓名「${A}」易被同名淹没；建议 --affiliation \"机构\" 或 --expert \"AU='${A}' AND SU='主题'\""
  fi
fi
if [[ -n "$AFF" ]]; then
  EXPERT=$(python3 - "$EXPERT" "$AFF" "$T" "$A" <<'PY'
import re, sys
expert, aff, title, author = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
def clean(s):
    return re.sub(r"[《》〈〉“”‘’\"'———]", "", s).replace("'", " ").strip()
aff_c = clean(aff)
if not aff_c:
    print(expert)
    raise SystemExit
clause = "AF='%s'" % aff_c
if expert:
    print(expert + " AND " + clause)
    raise SystemExit
parts = []
ti = clean(title)
au = clean(author)
if ti:
    parts.append("TI='%s'" % ti)
if au:
    parts.append("AU='%s'" % au)
parts.append(clause)
print(" AND ".join(parts))
PY
)
  echo "AFFILIATION: $AFF -> $EXPERT"
fi

if [[ -n "$EXPERT" ]]; then
  "$NAV" "$EXPERTURL"
  sleep 3
  ZH=$(runjs_file "$DIR/cnki_chinese.js")
  echo "CHINESE_TAB: $ZH"
  sleep 2
  gen_expert_js "$EXPERT"
  echo "EXPERT: $(runjs_file "$EXPERTGEN")"
  sleep 3
else
  SURL=$(python3 - "$BASE" "$T" <<'PY'
import sys, urllib.parse, re
base, t = sys.argv[1], sys.argv[2]
kw = re.sub(r'[《》〈〉“”‘’"\'———]', '', t).strip()
print(base + urllib.parse.quote(kw))
PY
)
  "$NAV" "$SURL"
  sleep 3
  ZH=$(runjs_file "$DIR/cnki_chinese.js")
  echo "CHINESE_TAB: $ZH"
  sleep 2
fi

gen_js "$T" "$A"
INFO=""
page=1
for attempt in 1 2 3; do
  INFO=$(runjs_file "$GEN")
  if [[ "$INFO" == "?"* || -z "$INFO" || "$INFO" == empty* ]]; then sleep 3; INFO=$(runjs_file "$GEN"); fi
  echo "SEARCH[$T] try$attempt: $INFO"
  [[ "$INFO" == captcha* ]] && { echo "RESULT[$T]: CAPTCHA"; exit 2; }
  if [[ "$INFO" == empty* ]]; then
    echo "EMPTY: 仍暂无数据（先确认已在中文库；若已在则可能是限流）"
    sleep 8
    INFO=""
    continue
  fi
  if [[ "$INFO" == "?"* || "$INFO" == "0@@NOMATCH"* ]]; then
    sleep 4
    INFO=""
    continue
  fi
  break
done
[[ "$INFO" == empty* || -z "$INFO" ]] && { echo "RESULT[$T]: EMPTY"; exit 1; }
[[ "$INFO" != *@@MATCH@@* ]] && {
  CNT="${INFO%%@@*}"
  if [[ "$CNT" =~ ^[0-9]+$ ]] && (( CNT > 0 && page < PAGES )); then
    while (( page < PAGES )); do
      NEXT=$(runjs_file "$DIR/cnki_next.js")
      [[ "$NEXT" != next* ]] && break
      (( page++ ))
      sleep 3
      INFO=$(runjs_file "$GEN")
      echo "PAGE[$page]: $INFO"
      [[ "$INFO" == *@@MATCH@@* ]] && break
      [[ "$INFO" == captcha* ]] && { echo "RESULT[$T]: CAPTCHA"; exit 2; }
    done
  fi
  [[ "$INFO" != *@@MATCH@@* ]] && {
    AMNOTE=""
    [[ "$INFO" == *@@AM* ]] && AMNOTE="（有候选因作者不符被跳过，请核对作者名）"
    [[ "$INFO" == *@@MULTI* ]] && AMNOTE="${AMNOTE}（本页多条候选，未自动取首条）"
    echo "RESULT[$T]: AMBIGUOUS$AMNOTE"
    exit 1
  }
}
CNT="${INFO%%@@*}"
[[ "$CNT" == "0" || "$CNT" == "?"* || -z "$CNT" ]] && { echo "RESULT[$T]: NORESULT"; exit 1; }

ST=""
for _w in 1 2 3 4 5; do
  ST=$(page_kind)
  echo "PAGEKIND: $ST"
  [[ "$ST" == captcha* ]] && { echo "RESULT[$T]: CAPTCHA"; exit 2; }
  [[ "$ST" == fee* ]] && { echo "RESULT[$T]: FEE 该篇不在机构下载权限内（知网收费页），转题录或提示用户"; exit 5; }
  [[ "$ST" == detail* ]] && break
  sleep 2
done
if [[ "$ST" != detail* ]]; then
  echo "RESULT[$T]: NODETAIL 匹配后未到详情页（$ST）"
  exit 1
fi

RES=""
for _c in 1 2 3; do
  RES=$(runjs_file "$DIR/cnki_click.js")
  echo "CLICK: $RES"
  [[ "$RES" == captcha* ]] && { echo "RESULT[$T]: CAPTCHA"; exit 2; }
  [[ "$RES" == fee* ]] && { echo "RESULT[$T]: FEE 该篇不在机构下载权限内（知网收费页），转题录或提示用户"; exit 5; }
  [[ "$RES" == nolink* ]] && { sleep 2; continue; }
  break
done
[[ "$RES" == nolink* ]] && { echo "RESULT[$T]: NOLINK"; exit 3; }

SINCE=$(python3 -c "import time; print(int(time.time()))")
for _b in 1 2 3 4 5 6; do
  sleep 2
  ST=$(page_kind)
  echo "AFTERCLICK: $ST"
  [[ "$ST" == captcha* ]] && { echo "RESULT[$T]: CAPTCHA"; exit 2; }
  [[ "$ST" == fee* ]] && { echo "RESULT[$T]: FEE 该篇不在机构下载权限内（知网收费页），转题录或提示用户"; exit 5; }
  [[ "$ST" == order* || "$ST" == detail* ]] && break
done

if [[ -z "$A" ]]; then
  echo "RESULT[$T]: NOTFOUND 未给作者，无法按 *_作者.pdf 安全匹配落盘文件"
  exit 4
fi
CAND=""
for i in {1..20}; do
  sleep 2
  if find "$HOME/Downloads" -maxdepth 1 \( -name '*.crdownload' -o -name 'Unconfirmed *' \) -mmin -5 2>/dev/null | grep -q .; then
    continue
  fi
  CAND=$(python3 "$DIR/cnki_pick_dl.py" "$HOME/Downloads" "$A" "$SINCE")
  [[ -n "$CAND" ]] && break
done
mkdir -p "$F"
if [[ -n "$CAND" ]]; then
  mv -n "$CAND" "$F/" 2>/dev/null || mv "$CAND" "$F/"
  echo "RESULT[$T]: OK $(basename "$CAND")"
  python3 "$DIR/pdf_pages.py" "$F/$(basename "$CAND")"
else
  echo "RESULT[$T]: NOTFOUND"
  ls -lt ~/Downloads | head -5
  exit 4
fi
