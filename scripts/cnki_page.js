// 当前页类型：详情 / 订单 / 收费 / 验证码 / 其它。返回值保持简单，交给 shell 判断。
(function () {
  var href = location.href || '';
  var title = document.title || '';
  var t = document.body ? document.body.innerText.slice(0, 4000) : '';
  var login = /^https?:\/\/(?:login|passport)\.cnki\.net(?:\/|$)/i.test(href)
    || (Array.from(document.querySelectorAll('input[type="password"]')).some(function(e){
      return e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
    }) && /登录|统一认证|sign[ -]?in|log[ -]?in/i.test(title + t));
  var captchaEl = Array.prototype.filter.call(document.querySelectorAll('*'), function (e) {
    if (!e.textContent) return false;
    var s = e.textContent.trim();
    if (s !== '拖动下方拼图完成验证' && s.indexOf('请依次点击') !== 0) return false;
    var r = e.getBoundingClientRect();
    return r.width > 0 && r.top >= 0 && r.top < 2000;
  });
  if (
    login || captchaEl.length ||
    /拼图校验/.test(title) ||
    /bar\.cnki\.net\/bar\/verify/i.test(href) ||
    t.indexOf('请依次点击') > -1
  ) {
    return 'captcha@@' + href;
  }
  if (/bar\.cnki\.net\/bar\/fee/i.test(href)) return 'fee@@' + href;
  if (/kcms2\/article\/abstract/i.test(href)) return 'detail@@' + href;
  if (/bar\.cnki\.net/i.test(href)) return 'order@@' + href;
  return 'other@@' + href;
})();
