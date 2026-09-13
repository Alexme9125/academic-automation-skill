(function () {
  // Only article-level evidence. A journal or navigation OA label is insufficient.
  function all(selector) { return Array.from(document.querySelectorAll(selector)); }
  function visible(node) { return !!(node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden'); }
  var doi = (document.querySelector('meta[name="citation_doi"]') || {}).content || '';
  var meta = all('meta[name="citation_open_access"]').some(function (node) { return /^true$/i.test(node.content || ''); });
  var license = all('a[rel~="license"], article a[href*="creativecommons.org"], .article__body a[href*="creativecommons.org"]')
    .find(function (node) { return /^https?:\/\/(?:www\.)?creativecommons\.org\/(?:licenses|publicdomain)\//i.test(node.href || '') && visible(node); });
  var rights = all('meta[name="dc.Rights"], meta[name="DC.Rights"], meta[name="dc.rights"], meta[name="citation_license"]')
    .find(function (node) { return /https?:\/\/(?:www\.)?creativecommons\.org\/(?:licenses|publicdomain)\//i.test(node.content || ''); });
  var labels = all('.doi-access, .article-access, .article-header__access, .epub-section__access, article .open-access, .article-header .open-access')
    .filter(visible).map(function (node) { return (node.innerText || '').trim(); });
  var open = labels.find(function (label) { return /^(?:open access|free access|free full text)$/i.test(label); });
  return JSON.stringify({access: meta || license || rights || open ? 'free' : 'unknown', doi: doi,
    evidence: meta ? 'citation_open_access' : license ? license.href : rights ? rights.content : open || ''});
})();
