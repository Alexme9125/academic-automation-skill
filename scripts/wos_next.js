// 点检索结果「下一页」。成功后 URL 会从 /relevance/1 变成 /relevance/2。
(function(){
  var b = document.querySelector('button[aria-label="Top Next Page"]')
    || document.querySelector('button[aria-label*="Next Page" i]');
  if (!b) return 'none';
  if (b.disabled || b.getAttribute('aria-disabled') === 'true') return 'disabled';
  b.click();
  return 'clicked';
})()
