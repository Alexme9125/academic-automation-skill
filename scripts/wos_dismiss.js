// 关掉 OneTrust cookie 偏好层和 Pendo 问卷，避免挡住检索框。
(function(){
  var notes = [];
  var allow = document.getElementById('accept-recommended-btn-handler');
  if (allow) { allow.click(); notes.push('allow-cookies'); }
  var confirm = document.querySelector('.save-preference-btn-handler');
  if (!allow && confirm) { confirm.click(); notes.push('confirm-cookies'); }
  var closePc = document.getElementById('close-pc-btn-handler');
  if (closePc) { closePc.click(); notes.push('close-cookie-pc'); }
  document.querySelectorAll('[id^=pendo], ._pendo-guide, .pendo-overlay, [class*=pendo-base]').forEach(function(el){
    try { el.remove(); notes.push('removed-pendo'); } catch (e) { el.style.display = 'none'; }
  });
  return JSON.stringify({notes: notes, url: location.href});
})()
