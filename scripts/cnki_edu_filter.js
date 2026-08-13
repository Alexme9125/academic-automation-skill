// 检索页过滤教育类文献。不要用 assessment/science 子串：会把 scientific、life-cycle assessment 等工科论文算进来。
// 用词边界，且必须命中教育领域词（education/student/teacher/school/vocational 等）。
(function(){
  var re = /\b(education|educational|student|students|teacher|teachers|school|schools|university|universities|college|colleges|classroom|vocational|pedagog\w*|curriculum|literacy|instruction)\b/i;
  var rows = document.querySelectorAll('.result-table-list tbody tr, table tbody tr');
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var a = rows[i].querySelector('a[href*="kcms2/article/abstract"]');
    if (!a || (a.href && a.href.indexOf('anchor=') > -1)) continue;
    var t = (rows[i].innerText || '').replace(/\n+/g, ' | ');
    if (!re.test(t)) continue;
    out.push({
      i: out.length + 1,
      title: (a.textContent || '').replace(/\s+/g, ' ').trim(),
      text: t.slice(0, 400),
      href: a.href || ''
    });
  }
  return JSON.stringify({n: out.length, rows: out});
})()
