(function(){
  var EXPECT=__JSON__;
  var AUTHOR=__AUTHOR__;
  var norm=function(s){return (s||'').replace(/[\s:：，,。.、；;！!？?《》〈〉()（）\-—·“”‘’"']/g,'');};
  var t=document.body?document.body.innerText:'';
  var caps=Array.prototype.filter.call(document.querySelectorAll('*'),function(e){
    if(!e.textContent)return false;
    var s=e.textContent.trim();
    if(s!=='拖动下方拼图完成验证'&&s.indexOf('请依次点击')!==0)return false;
    var r=e.getBoundingClientRect();return r.width>0&&r.top>=0&&r.top<2000;});
  if(caps.length||/拼图校验/.test(document.title||''))return 'captcha';
  if(t.indexOf('暂无数据')>-1 && t.indexOf('请稍后')>-1)return 'empty';
  var m=t.match(/共找到\s*(\d+)\s*条/);
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
    var rt=tr?tr.innerText.replace(/\n+/g,' '):'';
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
  var r0=rrow?rrow.innerText.replace(/\n+/g,' ').slice(0,110):'';
  return c+'@@NOMATCH@@'+r0+(am?'@@AM':'');
})()
