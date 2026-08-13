// Scholink / 同类 OJS：/article/download/{id}/{galley} 才是落盘链接；/article/view/ 常返回 XML 或 PDF.js。
(function(){
  var links = Array.prototype.slice.call(document.querySelectorAll('a[href]'));
  var hits = links.filter(function(a){
    var h = (a.href || '').toLowerCase();
    var t = (a.textContent || '').toLowerCase();
    return h.indexOf('/article/download/') > -1 || t.indexOf('download this pdf') > -1
      || h.indexOf('.pdf') > -1 || h.indexOf('/download/') > -1;
  }).map(function(a){
    return (a.textContent || '').trim().slice(0, 40) + '@@' + a.href;
  });
  return hits.slice(0, 15).join('\n') || 'none';
})()
