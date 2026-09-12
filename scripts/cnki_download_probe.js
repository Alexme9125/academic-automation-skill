// Locate one visible CNKI download control without triggering a request.
(function () {
  var token = __TOKEN__;
  var visible = function (e) {
    var r = e.getBoundingClientRect(), style = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };
  var controls = Array.from(document.querySelectorAll('a,button,input[type="button"],input[type="submit"]'));
  var candidates = controls.filter(visible).map(function(e) {
    var label = (e.textContent || e.value || '').replace(/\s+/g, '');
    var kind = e.id === 'pdfDown' || /^PDF下载$/i.test(label) ? 'pdf'
      : e.id === 'cajDown' || /^CAJ下载$/i.test(label) ? 'caj' : '';
    return {element:e, kind:kind, label:label, href:e.getAttribute('href') || '', id:e.id || ''};
  }).filter(function(x){ return x.kind; });
  var kind = candidates.some(function(x){ return x.kind === 'pdf'; }) ? 'pdf' : 'caj';
  candidates = candidates.filter(function(x){ return x.kind === kind; });
  var identified = candidates.filter(function(x){ return x.id === (kind === 'pdf' ? 'pdfDown' : 'cajDown'); });
  if (identified.length === 1) candidates = identified;
  if (candidates.length !== 1) return JSON.stringify({status:candidates.length ? 'ambiguous' : 'no_link',
    candidate_count:candidates.length, url:location.href});
  var hit = candidates[0];
  hit.element.setAttribute('data-academic-download', token);
  return JSON.stringify({status:'selected', kind:kind, label:hit.label, id:hit.id, href:hit.href,
    inline_handler:!!hit.element.getAttribute('onclick'), url:location.href,
    selector:'[data-academic-download="' + token + '"]'});
})()
