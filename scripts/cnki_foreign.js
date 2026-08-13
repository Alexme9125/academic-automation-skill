// 点击知网检索页「外文」标签。过滤是客户端行为，不是 URL 参数：
// ?rlang=FOREIGN 无效；必须点 <a class="en" data-val="Foreign">，它会按当前 #txt_search 重检索。
(function(){
  var el = document.querySelector('a.en[data-val="Foreign"]')
        || document.querySelector('#switch-ChEn a.en')
        || document.querySelector('#switch-ChEn .en')
        || document.querySelector('a.en');
  if (!el) {
    var els = Array.prototype.slice.call(document.querySelectorAll('a,span,div,li'));
    el = els.find(function(e){
      return e.textContent && e.textContent.trim() === '外文'
        && e.getBoundingClientRect().width > 0 && e.children.length === 0;
    });
    if (!el) {
      els.forEach(function(e){
        if (e.textContent && e.textContent.trim() === '外文' && e.getBoundingClientRect().width > 0) el = e;
      });
    }
  }
  if (!el) return 'notfound';
  el.click();
  return 'clicked ' + el.tagName + ' cls=' + (el.className || '') + ' data-val=' + (el.getAttribute('data-val') || '');
})()
