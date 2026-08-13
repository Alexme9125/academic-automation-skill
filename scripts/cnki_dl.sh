#!/bin/zsh
# CNKI 单篇下载：题名检索 -> 归一化题名匹配 -> 详情页 -> PDF/CAJ 下载 -> 归档
# 用法: cnki_dl.sh "检索题名" "第一作者" "目标文件夹"
# 退出码: 0 成功 | 1 无结果/未匹配/空库 | 2 验证码(需人工) | 3 无下载链接 | 4 文件未落盘 | 64 参数错误
set -u
if [ $# -lt 3 ]; then
  echo "用法: cnki_dl.sh \"检索题名\" \"第一作者\" \"目标文件夹\""
  exit 64
fi
T="$1"; A="$2"; F="$3"
DIR="$(cd "$(dirname "$0")" && pwd)"
GEN=/tmp/cnki_search_gen.js
BASE='https://kns.cnki.net/kns8s/defaultresult/index?crossids=YSTT4HG0%2CLSTPFY1C%2CEMRPGLPA%2CJUP3MUPD%2CMPMFIG1A%2CWQ0UVIAA%2CBLZOG7CK%2CPWFIRAGL%2CNLBO1Z6R%2CNN3FJMUV&korder=SU&kw='

runjs_file() {
  osascript -e "set js to do shell script \"cat '$1'\"" \
            -e 'tell application "Google Chrome" to execute active tab of front window javascript js' 2>&1
}

gen_js() {
python3 - "$1" "$GEN" <<'PY'
import sys, json
t, out = sys.argv[1], sys.argv[2]
js = '''(function(){
  var EXPECT=__JSON__;
  var norm=function(s){return (s||'').replace(/[\\s:：，,。.、；;！!？?《》〈〉()（）\\-—·“”‘’"']/g,'');};
  var t=document.body?document.body.innerText:'';
  var caps=Array.prototype.filter.call(document.querySelectorAll('*'),function(e){
    if(!e.textContent||e.textContent.trim()!=='拖动下方拼图完成验证')return false;
    var r=e.getBoundingClientRect();return r.width>0&&r.top>=0&&r.top<2000;});
  if(caps.length)return 'captcha';
  if(t.indexOf('暂无数据')>-1 && t.indexOf('请稍后')>-1)return 'empty';
  var m=t.match(/共找到\\s*(\\d+)\\s*条/);
  var c=m?m[1]:'?';
  var l=Array.prototype.filter.call(document.querySelectorAll('a[href*="kcms2/article/abstract"]'),function(a){return a.href.indexOf('anchor=')<0;});
  var pick=null;
  for(var i=0;i<l.length;i++){
    var tx=norm(l[i].textContent);
    if(!tx)continue;
    if(tx===norm(EXPECT)||tx.indexOf(norm(EXPECT))>-1){pick=l[i];break;}
  }
  var row='';
  var ref=pick||l[0];
  if(ref){var tr=ref.closest('tr');if(tr)row=tr.innerText.replace(/\\n+/g,' ').slice(0,110);}
  if(pick){location.href=pick.href;return c+'@@MATCH@@'+row;}
  return c+'@@NOMATCH@@'+row;
})()'''
open(out, 'w', encoding='utf-8').write(js.replace('__JSON__', json.dumps(t, ensure_ascii=False)))
PY
}

sleep 2
gen_js "$T"
SURL=$(python3 -c "import urllib.parse,sys;print(sys.argv[1]+urllib.parse.quote(sys.argv[2]))" "$BASE" "$T")
INFO=""
for attempt in 1 2 3; do
  open -a "Google Chrome" "$SURL"
  sleep $((2 + attempt))
  # 语言库会跨检索保留。外文任务之后若不点回「中文」，中文题名会在外文库里变成「暂无数据」。
  ZH=$(runjs_file "$DIR/cnki_chinese.js")
  echo "CHINESE_TAB: $ZH"
  sleep 2
  INFO=$(runjs_file "$GEN")
  if [[ "$INFO" == "?"* || -z "$INFO" || "$INFO" == empty* ]]; then sleep 3; INFO=$(runjs_file "$GEN"); fi
  echo "SEARCH[$T] try$attempt: $INFO"
  [[ "$INFO" == captcha* ]] && { echo "RESULT[$T]: CAPTCHA"; exit 2; }
  if [[ "$INFO" == empty* ]]; then
    echo "EMPTY: 仍暂无数据（先确认已在中文库；若已在则可能是限流）"
    sleep 8
    continue
  fi
  # 页面未渲染完时是 ?@@NOMATCH@@，不要立刻当 AMBIGUOUS
  if [[ "$INFO" == "?"* || "$INFO" == "0@@NOMATCH"* ]]; then
    sleep 4
    continue
  fi
  break
done
[[ "$INFO" == empty* ]] && { echo "RESULT[$T]: EMPTY"; exit 1; }
[[ "$INFO" == *NOMATCH* ]] && { echo "RESULT[$T]: AMBIGUOUS"; exit 1; }
CNT="${INFO%%@@*}"
[[ "$CNT" == "0" || "$CNT" == "?"* || -z "$CNT" ]] && { echo "RESULT[$T]: NORESULT"; exit 1; }
sleep 2
RES=$(runjs_file "$DIR/cnki_click.js")
echo "CLICK: $RES"
[[ "$RES" == captcha* ]] && { echo "RESULT[$T]: CAPTCHA"; exit 2; }
[[ "$RES" == nolink* ]] && { echo "RESULT[$T]: NOLINK"; exit 3; }

# Chrome 先写成 Unconfirmed *.crdownload，数秒后才改名为 *_作者.pdf；固定 sleep 会误判 NOTFOUND
CAND=""
for i in {1..20}; do
  sleep 2
  if find "$HOME/Downloads" -maxdepth 1 \( -name '*.crdownload' -o -name 'Unconfirmed *' \) -mmin -5 2>/dev/null | grep -q .; then
    continue
  fi
  CAND=$(find "$HOME/Downloads" -maxdepth 1 \( -name "*_${A}.pdf" -o -name "*_${A}.caj" \) -mmin -5 2>/dev/null | head -1)
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
