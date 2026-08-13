// Springer：curl 返回 HTML。浏览器打开 content/pdf/{DOI}.pdf → 内嵌查看器 → Cmd+S → Save。
(function(){
  var links = Array.prototype.slice.call(document.querySelectorAll('a[href]'));
  var hits = links.filter(function(a){
    var h = (a.href || '').toLowerCase();
    var t = (a.textContent || '').toLowerCase();
    return h.indexOf('/content/pdf/') > -1 || h.indexOf('.pdf') > -1 || t.indexOf('download pdf') > -1;
  }).map(function(a){
    return (a.textContent || '').trim().slice(0, 40) + '@@' + a.href;
  });
  return hits.slice(0, 15).join('\n') || 'none';
})()
