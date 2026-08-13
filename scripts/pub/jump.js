// 在当前页把 location.href 跳到指定 URL（SAGE 等必须页内跳转才触发下载）。
// 由 oa_dl.sh 生成 /tmp 副本并替换 __URL__。
(function(){
  location.href = __URL__;
  return 'jumped';
})()
