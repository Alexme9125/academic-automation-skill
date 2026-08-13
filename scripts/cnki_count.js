// 提取「共找到 N 条」。任何过滤/切库点击后必须再跑一次，核对计数是否变化。
// 学科筛选等点击后计数不变 = 未生效，不要当成成功。
(function(){
  var t = document.body ? document.body.innerText : '';
  var all = t.match(/共找到[^\n]{0,80}/g);
  var n = t.match(/共找到\s*([\d,]+)\s*条/);
  return JSON.stringify({
    raw: all ? all.join('||') : 'none',
    n: n ? parseInt(n[1].replace(/,/g, ''), 10) : null
  });
})()
