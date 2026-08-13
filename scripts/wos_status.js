// WoS 当前页状态：登录墙 / 人机验证 / 检索页种类。机构名只报有无，不回传具体学校。
(function(){
  function txt(el){ return el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  var url = location.href || '';
  var title = document.title || '';
  var body = (document.body && document.body.innerText || '').slice(0, 2500);
  var login = /access\.clarivate\.com\/login/i.test(url)
    || /you (do not|don't) have access|ip.?error|not licensed|institutional login required/i.test(body)
    || (title === 'Clarivate' && !document.getElementById('search-option-0') && !document.querySelector('app-record'));
  var captcha = /captcha|are you a robot|unusual traffic|hcaptcha|recaptcha/i.test(body + ' ' + title);
  var kind = 'other';
  if (login) kind = 'login';
  else if (/\/wos\/[^/]+\/summary\//i.test(url)) kind = 'summary';
  else if (/\/full-record\//i.test(url)) kind = 'full';
  else if (document.getElementById('search-option-0')) kind = 'basic';
  else if (document.getElementById('composeQuerySmartSearch')) kind = 'smart';
  var stats = (title.match(/[–—-]\s*([\d,]+)\s*[–—-]/) || [])[1] || '';
  var inst = !!(document.getElementById('InstLogoTa-0') || document.getElementById('promo-signIn-link'));
  return JSON.stringify({
    login: login,
    captcha: captcha,
    kind: kind,
    institution: inst,
    hasBasic: !!document.getElementById('search-option-0'),
    hasSmart: !!document.getElementById('composeQuerySmartSearch'),
    nRecords: document.querySelectorAll('app-record').length,
    stats: stats,
    url: url,
    title: title
  });
})()
