// Nature (Scientific Reports 等)：curl https://www.nature.com/articles/{id}.pdf 带 UA 即可。
(function(){
  var links = Array.prototype.slice.call(document.querySelectorAll('a[href]'));
  var pdfs = links.filter(function(a){
    var t = (a.textContent || '').toLowerCase();
    var h = (a.href || '').toLowerCase();
    return /\/articles\/[^/]+\.pdf/.test(h) || t.indexOf('download pdf') > -1 || h.indexOf('.pdf') > -1;
  }).map(function(a){
    return (a.textContent || '').trim().slice(0, 40) + '@@' + a.href;
  });
  return pdfs.slice(0, 12).join('\n') || 'none';
})()
