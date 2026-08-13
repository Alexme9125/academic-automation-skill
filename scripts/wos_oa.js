// 勾选侧栏 Quick Filters 的 Open Access，再点该组 Refine。点完必须再读标题里的条数。
(function(){
  var cb = document.querySelector('input.mdc-checkbox__native-control[aria-label^="Open Access"]');
  if (!cb) return JSON.stringify({ok: false, err: 'no Open Access checkbox', title: document.title});
  if (!cb.checked) cb.click();
  var refine = document.querySelector('.refine-button.mdc-button--unelevated');
  if (refine) refine.click();
  return JSON.stringify({ok: true, checked: cb.checked, refine: !!refine, title: document.title, url: location.href});
})()
