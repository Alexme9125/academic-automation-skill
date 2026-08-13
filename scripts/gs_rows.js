// 谷歌学术检索页抽题录。结果卡片：.gs_r.gs_or / .gs_ri；题名 h3.gs_rt a；作者行 .gs_a；摘要 .gs_rs。
// 若命中 captcha/unusual traffic，返回 {captcha:true}，不要继续翻页。
(function(){
  function txt(el){ return el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  var body = document.body ? document.body.innerText : '';
  var captcha = /unusual traffic|not a robot|Enable JavaScript|人机身份|验证码/i.test(body.slice(0, 2000))
    || /sorry\/index|ipv4\/sorry/i.test(location.href);
  if (captcha) return JSON.stringify({captcha: true, url: location.href, title: document.title, n: 0, rows: []});
  var stats = (body.match(/About\s+[\d,]+\s+results/i) || body.match(/约\s*[\d,]+\s*条/) || [''])[0];
  var cards = document.querySelectorAll('.gs_r.gs_or');
  if (!cards.length) cards = document.querySelectorAll('.gs_ri');
  var rows = [];
  for (var i = 0; i < cards.length; i++) {
    var c = cards[i];
    var ri = c.querySelector('.gs_ri') || c;
    var ta = ri.querySelector('h3.gs_rt a');
    var title = txt(ri.querySelector('h3.gs_rt')).replace(/^(\[PDF\]|\[HTML\]|\[CITATION\]|\[BOOK\]|\[B\])\s*/i, '').trim();
    var authors = txt(ri.querySelector('.gs_a'));
    var snippet = txt(ri.querySelector('.gs_rs'));
    var year = '';
    var ym = authors.match(/\b(19|20)\d{2}\b/g);
    if (ym) year = ym[ym.length - 1];
    var cited = '';
    Array.prototype.slice.call(ri.querySelectorAll('.gs_fl a, .gs_flb a')).forEach(function(a){
      var t = txt(a);
      if (/Cited by|被引用次数/i.test(t)) cited = t.replace(/[^\d]/g, '');
    });
    var pdf = '';
    var pdfA = c.querySelector('.gs_or_ggsm a, .gs_ggs a');
    if (pdfA) pdf = pdfA.href;
    if (!pdf) {
      Array.prototype.slice.call(c.querySelectorAll('a')).forEach(function(a){
        var h = (a.href || '').toLowerCase();
        var t = txt(a).toLowerCase();
        if (!pdf && (/\.pdf(\?|$)/.test(h) || t === '[pdf]')) pdf = a.href;
      });
    }
    if (!title) continue;
    rows.push({
      i: rows.length + 1,
      title: title,
      href: ta ? ta.href : '',
      authors_line: authors,
      year: year,
      snippet: snippet.slice(0, 500),
      cited: cited,
      pdf: pdf
    });
  }
  var next = document.querySelector('a.gs_nma[aria-label="Next"], a[aria-label="Next"], #gs_n td:last-child a');
  return JSON.stringify({captcha: false, stats: stats, url: location.href, n: rows.length, next: next ? next.href : '', rows: rows});
})()
