(function(){
  var KEYWORD = __QUERY__;
  var el = document.getElementById('search-option-0');
  if (!el) return JSON.stringify({ok:false, err:'no #search-option-0'});
  el.focus();
  var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(el, KEYWORD);
  el.dispatchEvent(new Event('input', {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
  var btn = null;
  document.querySelectorAll('button').forEach(function(b){
    var t = (b.textContent || '').replace(/\s+/g, ' ').trim();
    if (/search Search/i.test(t) || t === 'Search') btn = b;
  });
  if (!btn) return JSON.stringify({ok:false, err:'no Search button', value:el.value});
  if (btn.disabled) {
    btn.disabled = false;
    btn.removeAttribute('disabled');
  }
  btn.click();
  return JSON.stringify({ok:true, value:el.value});
})()
