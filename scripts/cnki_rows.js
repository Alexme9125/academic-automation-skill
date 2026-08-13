// 检索页提取所有结果行：序号 / 题名 / 行内文本 / 完整 abstract 链接。
(function(){
  var rows = document.querySelectorAll('.result-table-list tbody tr, table tbody tr');
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var a = rows[i].querySelector('a[href*="kcms2/article/abstract"]');
    if (!a || (a.href && a.href.indexOf('anchor=') > -1)) continue;
    var t = (rows[i].innerText || '').replace(/\n+/g, ' | ');
    out.push({
      i: out.length + 1,
      title: (a.textContent || '').replace(/\s+/g, ' ').trim(),
      text: t.slice(0, 400),
      href: a.href || ''
    });
  }
  return JSON.stringify({n: out.length, rows: out});
})()
