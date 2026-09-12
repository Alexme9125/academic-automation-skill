// 通用：页面内 PDF / download 链接。各出版社落地页先用它摸底。
(function(){
  var out = Array.from(document.querySelectorAll('meta[name="citation_pdf_url"]')).map(function(m){
    return {label:'Article PDF', url:new URL(m.content, location.href).href, source:'citation_pdf_url'};
  });
  var links = Array.prototype.slice.call(document.querySelectorAll('a[href]'));
  var pdfs = links.filter(function(a){
    var t = (a.textContent || '').toLowerCase();
    var h = (a.href || '').toLowerCase();
    return t.indexOf('pdf') > -1 || h.indexOf('.pdf') > -1 || h.indexOf('download') > -1
      || h.indexOf('/uploadfile/') > -1;
  }).map(function(a){
    return {label:(a.textContent || '').trim().replace(/\s+/g,' ').slice(0,120), url:a.href,
      supplement:!!a.closest('[id*="supplement"], [class*="supplement"], [id*="appendix"], [class*="appendix"]')};
  });
  return JSON.stringify(out.concat(pdfs).slice(0,50));
})()
