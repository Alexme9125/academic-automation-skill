// Stemmpress / Aeph.press 等：页面内 /uploadfile/....pdf 可 curl。
(function(){
  var links = Array.prototype.slice.call(document.querySelectorAll('a[href]'));
  var hits = links.filter(function(a){
    var h = (a.href || '').toLowerCase();
    return h.indexOf('/uploadfile/') > -1 && h.indexOf('.pdf') > -1;
  }).map(function(a){
    return (a.textContent || '').trim().slice(0, 40) + '@@' + a.href;
  });
  return hits.slice(0, 15).join('\n') || 'none';
})()
