// 点击知网检索页「中文」标签。语言库是客户端状态，会跨检索保留：
// 刚跑过外文检索时，新打开的中文题名检索仍停在外文库，表现为「暂无数据」，并不是限流。
(function(){
  var el = document.querySelector('a.ch[data-val="Chinese"]')
        || document.querySelector('#switch-ChEn a.ch')
        || document.querySelector('.switch-ChEn a.ch')
        || document.querySelector('a.ch');
  if (!el) {
    var els = Array.prototype.slice.call(document.querySelectorAll('a,span,div,li'));
    el = els.find(function(e){
      return e.textContent && e.textContent.trim() === '中文'
        && e.getBoundingClientRect().width > 0 && e.children.length === 0;
    });
  }
  if (!el) return 'notfound';
  el.click();
  return 'clicked ' + el.tagName + ' cls=' + (el.className || '') + ' data-val=' + (el.getAttribute('data-val') || '');
})()
