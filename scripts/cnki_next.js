// 检索结果页点「下一页」。配合 cnki_dl.sh 的 --pages 自动翻页匹配。
(function(){
  var b = document.querySelector('#PageNext') || document.querySelector('a#PageNext');
  if (!b || !b.getClientRects().length || b.getAttribute('disabled') !== null || b.getAttribute('aria-disabled') === 'true' || /disabled/i.test(b.className)) return 'nobtn';
  b.click();
  return 'next';
})()
