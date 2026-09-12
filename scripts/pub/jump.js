// Call only after the publisher article page passed the challenge/login probe.
// The download attribute is a same-origin hint; cross-origin links use navigation.
(function(){
  var target = new URL(__URL__, location.href);
  if (target.origin === location.origin) {
    var a = document.createElement('a');
    a.href = target.href;
    a.download = __NAME__;
    document.body.appendChild(a);
    a.click();
    a.remove();
    return 'download-requested';
  }
  location.href = target.href;
  return 'jumped';
})()
