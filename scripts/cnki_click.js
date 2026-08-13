(function(){
  var caps = Array.prototype.filter.call(document.querySelectorAll('*'), function(e){
    if (!e.textContent || e.textContent.trim() !== '拖动下方拼图完成验证') return false;
    var r = e.getBoundingClientRect();
    return r.width > 0 && r.top >= 0 && r.top < 2000;
  });
  if (caps.length) return 'captcha';
  var pdf = Array.prototype.filter.call(document.querySelectorAll('a'), function(a){ return a.textContent.trim() === 'PDF下载'; });
  var caj = Array.prototype.filter.call(document.querySelectorAll('a'), function(a){ return a.textContent.trim() === 'CAJ下载'; });
  var a = pdf.length ? pdf[0] : (caj.length ? caj[0] : null);
  if (!a) return 'nolink@@' + document.title;
  var kind = pdf.length ? 'pdf' : 'caj';
  location.href = a.href;
  return kind + '@@' + document.title;
})()
