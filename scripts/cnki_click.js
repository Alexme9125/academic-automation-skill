(function(){
  var href = location.href || '';
  var title = document.title || '';
  var body = document.body ? document.body.innerText.slice(0, 2000) : '';
  var caps = Array.prototype.filter.call(document.querySelectorAll('*'), function(e){
    if (!e.textContent) return false;
    var s = e.textContent.trim();
    if (s !== '拖动下方拼图完成验证' && s.indexOf('请依次点击') !== 0) return false;
    var r = e.getBoundingClientRect();
    return r.width > 0 && r.top >= 0 && r.top < 2000;
  });
  if (caps.length || /拼图校验/.test(title) || /bar\.cnki\.net\/bar\/verify/i.test(href) || body.indexOf('请依次点击') > -1) return 'captcha';
  if (/bar\.cnki\.net\/bar\/fee/i.test(href)) return 'fee';
  var pdf = Array.prototype.filter.call(document.querySelectorAll('a'), function(a){ return a.textContent.trim() === 'PDF下载'; });
  var caj = Array.prototype.filter.call(document.querySelectorAll('a'), function(a){ return a.textContent.trim() === 'CAJ下载'; });
  var a = pdf.length ? pdf[0] : (caj.length ? caj[0] : null);
  if (!a) return 'nolink@@' + document.title;
  var kind = pdf.length ? 'pdf' : 'caj';
  location.href = a.href;
  return kind + '@@' + document.title;
})()
