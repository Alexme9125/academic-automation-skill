// 详情页提取完整 DOI（含 10.53469/JRVE.2025.7(09).12 这类括号段）和 doi.org 链接。
// 知网头部 DOI 常被截断；以最长候选为准。
(function(){
  function pickAll(text) {
    if (!text) return [];
    var re = /10\.\d{4,9}\/[^\s<>"'，。；、]+/g;
    var found = [], m;
    while ((m = re.exec(text))) {
      var d = m[0].replace(/[.,;:]+$/, '');
      var open = (d.match(/\(/g) || []).length;
      var close = (d.match(/\)/g) || []).length;
      while (close > open) {
        d = d.replace(/\)+([.,;:]?)$/, '$1').replace(/[.,;:]+$/, '');
        close--;
      }
      if (/^10\.\d{4,9}\/.+/.test(d) && found.indexOf(d) < 0) found.push(d);
    }
    found.sort(function(a, b){ return b.length - a.length; });
    return found;
  }
  var body = document.body ? document.body.innerText : '';
  var fromBody = pickAll(body);
  var hrefs = Array.prototype.slice.call(document.querySelectorAll('a[href]')).filter(function(x){
    var h = (x.href || '').toLowerCase();
    return h.indexOf('doi.org') > -1 || /10\.\d{4,9}\//.test(h);
  }).map(function(x){
    return (x.textContent || '').trim().slice(0, 40) + '@@' + x.href.slice(0, 180);
  });
  var fromHref = [];
  hrefs.forEach(function(line){
    pickAll(line).forEach(function(d){ if (fromHref.indexOf(d) < 0) fromHref.push(d); });
  });
  var best = (fromBody[0] && fromHref[0])
    ? (fromBody[0].length >= fromHref[0].length ? fromBody[0] : fromHref[0])
    : (fromBody[0] || fromHref[0] || '');
  return JSON.stringify({
    doi: best,
    body_dois: fromBody.slice(0, 5),
    href_dois: fromHref.slice(0, 5),
    hrefs: hrefs.slice(0, 8)
  });
})()
