// 结果列表是窗口滚动懒加载：不滚只会抽到前几条。重复执行直到 title 数不再增加。
(function(){
  var before = document.querySelectorAll('a[data-ta="summary-record-title-link"]').length;
  window.scrollBy(0, 900);
  var list = document.querySelector('app-records-list');
  if (list && list.scrollHeight > list.clientHeight + 20) list.scrollTop += 800;
  return JSON.stringify({before: before, after: document.querySelectorAll('a[data-ta="summary-record-title-link"]').length, y: window.scrollY});
})()
