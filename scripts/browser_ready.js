// Read-only readiness probe. Content must remain stable across observations.
(function () {
  var o = __OPTIONS__, url = location.href, title = document.title || '';
  var body = document.body ? document.body.innerText : '';
  function visible(el) { return !!(el && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden'); }
  var cnkiCaptcha = Array.from(document.querySelectorAll('*')).some(function(e){
    var s = (e.textContent || '').trim();
    if (s !== '拖动下方拼图完成验证' && s.indexOf('请依次点击') !== 0) return false;
    var r = e.getBoundingClientRect();
    return visible(e) && r.width > 0 && r.top >= 0 && r.top < Math.min(2000, window.innerHeight);
  });
  var captcha = /bar\.cnki\.net\/bar\/verify|sorry\/index|ipv4\/sorry/.test(url)
    || /拼图校验|unusual traffic|are you a robot|verify (?:that )?you are human|checking your browser|正在进行安全验证|请完成安全验证/i.test(title + body.slice(0, 2000))
    || /^(?:just a moment|attention required|security (?:check|verification))/i.test(title)
    || Array.from(document.querySelectorAll('#challenge-running, #challenge-stage, #awswaf-captcha-container')).some(visible)
    || cnkiCaptcha;
  var login = /access\.clarivate\.com\/login/.test(url)
    || /institutional login required/i.test(body.slice(0, 2500))
    || (Array.from(document.querySelectorAll('input[type="password"]')).some(visible)
      && /登录|统一认证|sign[ -]?in|log[ -]?in|authentication/i.test(title + body.slice(0, 2500)));
  var loading = Array.from(document.querySelectorAll('[aria-busy="true"], .loading, .loading-mask, mat-spinner')).some(visible);
  var empty = /暂无数据|没有找到|did not match any articles|No results found/i.test(body);
  var notFound = /(?:^|\s)404(?:\s|$)|page not found|页面不存在|页面未找到/i.test(title)
    || (body.length < 1500 && /404\s*(?:not found|错误)|页面不存在|页面未找到/i.test(body));
  var ready = false, content = '', mode = o.mode;
  if (mode === 'cnki-form') ready = !!document.querySelector('#txt_search, textarea.textarea-major, .switch-ChEn a[data-val]');
  if (mode === 'expert') ready = !!document.querySelector('textarea.textarea-major');
  if (mode === 'cnki-results') {
    content = Array.from(document.querySelectorAll('a[href*="kcms2/article/abstract"]')).map(function(a){return a.href + a.textContent;}).join('|');
    ready = !!content || empty;
  }
  if (mode === 'cnki-meta') {
    ready = /kcms2\/article\/abstract/.test(url) && body.length > 200
      && /摘要|Abstract|作者|Author|DOI/i.test(body) && !!title;
    content = body;
  }
  if (mode === 'cnki-detail') ready = /kcms2\/article\/abstract/.test(url)
    && Array.from(document.querySelectorAll('a')).some(function(a){return /^(PDF下载|CAJ下载)$/.test(a.textContent.trim());});
  if (mode === 'scholar') {
    content = Array.from(document.querySelectorAll('.gs_r.gs_or, .gs_ri')).map(function(e){return e.textContent;}).join('|');
    ready = /\/scholar/.test(url) && (!!content || empty);
  }
  if (mode === 'wos-basic') ready = !!document.querySelector('#search-option-0');
  if (mode === 'wos-results') {
    content = Array.from(document.querySelectorAll('a[data-ta="summary-record-title-link"]')).map(function(a){return a.href;}).join('|');
    ready = /\/summary\//.test(url) && (!!content || empty);
  }
  if (mode === 'publisher') { ready = body.length > 150; content = title + body.length; }
  if (o.url) {
    var expected = new URL(o.url), actual = new URL(url);
    // Exact page/query checks prevent consuming the prior page during navigation.
    ready = ready && actual.hostname === expected.hostname && actual.pathname === expected.pathname;
    ['q', 'start', 'kw', 'filename', 'dbname', 'v'].forEach(function(k){
      if (expected.searchParams.has(k) && actual.searchParams.get(k) !== expected.searchParams.get(k)) ready = false;
    });
  }
  var hash = 2166136261;
  for (var i=0;i<content.length;i++) hash = Math.imul(hash ^ content.charCodeAt(i), 16777619);
  return JSON.stringify({url:url, ready:ready && !loading && document.readyState !== 'loading',
    empty:empty, captcha:captcha, login:login, not_found:notFound, fee:/bar\.cnki\.net\/bar\/fee/.test(url),
    signature:url + '|' + (hash >>> 0)});
})()
