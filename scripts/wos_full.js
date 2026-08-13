// WoS 详情页（/wos/woscc/full-record/WOS:…）抽 DOI、年、全文入口。正文常写成 DOI10.xxxx 中间无空格。
(function(){
  function txt(el){ return el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  var body = (document.body && document.body.innerText) || '';
  var doi = '';
  document.querySelectorAll('a').forEach(function(a){
    var h = a.href || '';
    var m = h.match(/doi\.org\/(10\.[^?#]+)/i) || h.match(/KeyAID=([^&]+)/);
    if (m && !doi) doi = decodeURIComponent(m[1]);
  });
  var dm = body.match(/DOI\s*(10\.\d{4,9}\/[^\s]+)/i) || body.match(/\b(10\.\d{4,9}\/[-._;()/:A-Z0-9]+)/i);
  if (dm && !doi) doi = dm[1].replace(/[.,;]+$/, '');
  doi = (doi || '').replace(/^DOI/i, '').trim();
  var ut = (location.href.match(/WOS:\d+/) || body.match(/WOS:\d+/) || [''])[0];
  var year = '';
  var ym = body.match(/\bPublished\s+[A-Z]*\s*((?:19|20)\d{2})\b/i) || body.match(/\n((?:19|20)\d{2})\n/);
  if (ym) year = ym[1];
  var titleEl = document.querySelector('h1, app-full-record-title, .title');
  var title = txt(document.querySelector('h2.title, app-full-record-title h1')) || (document.title || '').replace(/-Web of Science.*$/i, '').trim();
  if (titleEl && txt(titleEl).length > 10) title = txt(titleEl);
  var ft = [];
  document.querySelectorAll('a.full-record-link, a[id^="FRLinkTa-link"]').forEach(function(a){
    var t = txt(a);
    if (t) ft.push({label: t.slice(0, 120), href: a.href});
  });
  var oa = /Open Access/i.test(body.slice(0, 4000)) || !!document.querySelector('[data-mat-icon-name="open-access"]');
  var src = '';
  var sm = body.match(/Source\s*\n([^\n]+)/);
  if (sm) src = sm[1].replace(/arrow_back|View Journal Impact/g, '').trim();
  return JSON.stringify({
    url: location.href,
    title: title,
    doi: doi,
    ut: ut,
    year: year,
    source: src,
    oa: oa,
    ft: ft,
    page_title: document.title
  });
})()
