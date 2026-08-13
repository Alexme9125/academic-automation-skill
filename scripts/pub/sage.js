// SAGE：curl 一律 403。页内跳转 journals.sagepub.com/doi/pdf/{DOI}?download=true 可触发下载。
(function(){
  var links = Array.prototype.slice.call(document.querySelectorAll('a[href]'));
  var pdfs = links.filter(function(a){
    var t = (a.textContent || '').toLowerCase();
    var h = (a.href || '').toLowerCase();
    return h.indexOf('/doi/pdf') > -1 || t.indexOf('pdf') > -1 || h.indexOf('download=true') > -1;
  }).map(function(a){
    return (a.textContent || '').trim().slice(0, 40) + '@@' + a.href;
  });
  return pdfs.slice(0, 15).join('\n') || 'none';
})()
