// SCIRP：content.scirp.org/pdf/{id}.pdf 可直接 curl。
(function(){
  var links = Array.prototype.slice.call(document.querySelectorAll('a[href]'));
  var pdfs = links.filter(function(a){
    var h = (a.href || '').toLowerCase();
    return h.indexOf('content.scirp.org') > -1 || h.indexOf('.pdf') > -1;
  }).map(function(a){
    return (a.textContent || '').trim().slice(0, 40) + '@@' + a.href;
  });
  return pdfs.slice(0, 12).join('\n') || 'none';
})()
