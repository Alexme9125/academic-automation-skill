// 通用：页面内 PDF / download 链接。各出版社落地页先用它摸底。
(function(){
  var links = Array.prototype.slice.call(document.querySelectorAll('a[href]'));
  var pdfs = links.filter(function(a){
    var t = (a.textContent || '').toLowerCase();
    var h = (a.href || '').toLowerCase();
    return t.indexOf('pdf') > -1 || h.indexOf('.pdf') > -1 || h.indexOf('download') > -1
      || h.indexOf('/uploadfile/') > -1;
  }).map(function(a){
    return (a.textContent || '').trim().slice(0, 40) + '@@' + a.href;
  });
  return pdfs.slice(0, 20).join('\n') || 'none';
})()
