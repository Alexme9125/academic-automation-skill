// WoS Core Collection 检索结果页抽题录。卡片：app-record（虚拟列表，未滚到的行没有 title-link）。
// 摘要页 DOI 常只出现在 DestApp=DOI 的 KeyAID= 参数里；GetFTR「Free Full Text」行往往没有 DOI，需开 full-record。
(function(){
  function txt(el){ return el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  var recs = document.querySelectorAll('app-record');
  var rows = [];
  for (var i = 0; i < recs.length; i++) {
    var r = recs[i];
    var titleA = r.querySelector('a[data-ta="summary-record-title-link"]') || r.querySelector('a.title-link');
    if (!titleA) continue;
    var authors = [];
    r.querySelectorAll('a.authors').forEach(function(a){
      var t = txt(a);
      if (t && authors.indexOf(t) < 0) authors.push(t);
    });
    var sourceA = r.querySelector('a.summary-source-title-link');
    var doi = '';
    var ft = '';
    var fta = '';
    var acc = '';
    r.querySelectorAll('a').forEach(function(a){
      var h = a.href || '';
      var t = txt(a);
      var m = h.match(/KeyAID=([^&]+)/);
      if (m && !doi) doi = decodeURIComponent(m[1]);
      var m2 = h.match(/\/full-record\/(WOS:\d+)/i);
      if (m2) acc = m2[1];
      if (/Free Full Text|Full Text from Publisher|Full Text at Publisher|View [Ff]ull [Tt]ext|View Full Text on /i.test(t) && !ft) {
        ft = t.replace(/\s+for\s+.*/i, '').trim();
        fta = h;
      }
    });
    var ds = r.querySelector('.data-section');
    var lines = ds ? ds.innerText.split('\n').map(function(s){ return s.trim(); }).filter(Boolean) : [];
    var year = '';
    for (var k = 0; k < lines.length; k++) {
      if (/^(19|20)\d{2}$/.test(lines[k])) { year = lines[k]; break; }
    }
    var oa = !!r.querySelector('[aria-label="Open Access"], [data-mat-icon-name="open-access"]');
    rows.push({
      i: rows.length + 1,
      title: txt(titleA),
      href: titleA.href,
      authors: authors.join('; '),
      source: sourceA ? txt(sourceA).replace(/arrow_drop_down/g, '').trim() : '',
      year: year,
      doi: doi,
      ut: acc,
      oa: oa,
      ft: ft,
      ft_url: fta
    });
  }
  var stats = (document.title.match(/[–—-]\s*([\d,]+)\s*[–—-]/) || [])[1] || '';
  var nextBtn = document.querySelector('button[aria-label="Top Next Page"], button[aria-label*="Next Page" i]');
  var nextOn = !!(nextBtn && !nextBtn.disabled && nextBtn.getAttribute('aria-disabled') !== 'true');
  var bodyHead = (document.body && document.body.innerText || '').slice(0, 800);
  var captcha = /captcha|are you a robot|unusual traffic/i.test(bodyHead + ' ' + document.title);
  var login = /access\.clarivate\.com\/login/i.test(location.href);
  return JSON.stringify({
    captcha: captcha,
    login: login,
    stats: stats,
    url: location.href,
    title: document.title,
    n: rows.length,
    next: nextOn,
    rows: rows
  });
})()
