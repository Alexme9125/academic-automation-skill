// 知网 kcms2 详情页元数据。DOI 取最长候选（含括号版本），覆盖头部截断的短 DOI。
// 输出 JSON。诊断完整 DOI 来源也可另跑 cnki_full_doi.js。
(function(){
  function pickLongestDoi(text) {
    if (!text) return '';
    var re = /10\.\d{4,9}\/[^\s<>"'，。；、]+/g;
    var found = [], m;
    while ((m = re.exec(text))) {
      var d = m[0].replace(/[.,;:]+$/, '');
      var open = (d.match(/\(/g) || []).length;
      var close = (d.match(/\)/g) || []).length;
      while (close > open) {
        d = d.replace(/\)+([.,;:]?)$/, '$1').replace(/[.,;:]+$/, '');
        close--;
      }
      if (/^10\.\d{4,9}\/.+/.test(d)) found.push(d);
    }
    found.sort(function(a, b){ return b.length - a.length; });
    return found[0] || '';
  }
  function hrefDois() {
    var out = [];
    Array.prototype.slice.call(document.querySelectorAll('a[href]')).forEach(function(a){
      var h = a.href || '';
      var m = h.match(/doi\.org\/(10\.\d{4,9}\/[^\s?#]+)/i);
      if (m) out.push(decodeURIComponent(m[1]));
      var d = pickLongestDoi(h);
      if (d) out.push(d);
    });
    out.sort(function(a, b){ return b.length - a.length; });
    return out;
  }

  var t = document.title.replace(/\s*-\s*中国知网$/, '').trim();
  var body = document.body ? document.body.innerText : '';
  var lines = body.split('\n').map(function(s){ return s.trim(); }).filter(Boolean);
  var out = {title: t, doi: '', doi_header: '', authors: '', journal: '', year: '', abstract: '', doi_hrefs: []};
  var m;
  for (var i = 0; i < lines.length; i++) {
    var l = lines[i];
    if (!out.doi_header) {
      m = l.match(/DOI[：:]\s*(10\.\d{4,9}\/[^\s]+)/i);
      if (m) out.doi_header = m[1].replace(/[.,;]+$/, '');
    }
    if (!out.authors && /^(作者|Author)s?[：:]/i.test(l)) {
      out.authors = l.replace(/^(作者|Author)s?[：:]\s*/i, '').slice(0, 300);
    }
    if (!out.journal) {
      m = l.match(/^(?:Journal|刊名|来源|Source)\s*[|：:]\s*(?:\[J\]\s*)?(.+)$/i);
      if (m) out.journal = m[1].replace(/\s*Volume\b.*$/i, '').replace(/\s*国际期刊.*$/, '').replace(/\s+/g, ' ').trim().slice(0, 160);
    }
    if (!out.year) {
      m = l.match(/^(Year|年[份份]|出版日期|Publication Date)[：:].*?(\d{4})/i);
      if (m) out.year = m[2];
    }
  }
  if (!out.year) {
    m = body.match(/\b(19|20)\d{2}\b/);
    if (m) out.year = m[0];
  }
  var slice = '';
  m = body.match(/Abstract\s*\/\s*摘要[\s\S]{0,80}?(?:MT翻译\s*)?([A-Za-z][\s\S]{40,900})/);
  if (m) slice = m[1];
  if (!slice) {
    m = body.match(/\bAbstract\b[:\s]*([A-Za-z][\s\S]{40,900})/);
    if (m) slice = m[1];
  }
  if (!slice) {
    m = body.match(/摘要[\s\S]{0,40}?([^\n]{40,900})/);
    if (m) slice = m[1];
  }
  if (slice) {
    out.abstract = slice.replace(/\s+/g, ' ').replace(/\s*(关键词|相似文献|相关服务|参考文献).*$/, '').trim().slice(0, 600);
  }
  var hrefs = hrefDois();
  out.doi_hrefs = hrefs.slice(0, 5);
  var candidates = [out.doi_header].concat(hrefs);
  candidates.push(pickLongestDoi(body));
  candidates = candidates.filter(Boolean).sort(function(a, b){ return b.length - a.length; });
  out.doi = candidates[0] || '';
  return JSON.stringify(out);
})()
