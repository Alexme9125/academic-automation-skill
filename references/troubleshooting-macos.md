# macOS 排错（仅在失败或维护时读取）

## 中文题名与专业检索

- `NOMATCH/AMBIGUOUS`：核对结果行作者和题名。相似题名《…的应用》与《…的应用策略》不是同一篇；不取多候选的首条。短姓名用 `--affiliation "机构"` 或 `--expert "AU='姓名' AND AF='机构'"` / `AND SU='主题'` 收窄。不要把真实学校名提交到仓库。
- 中文题名在外文库显示“暂无数据”不是限流；先确认已点回中文。确在中文库仍无结果，再核对检索式或等待 60–180 秒。
- 普通单篇搜索使用 `korder=TI`；作者名不是题名/主题词。题名里的《》〈〉弯引号和破折号由脚本清理；仍无结果时拆 token，例如 `TI='K-12' AND SU='学习进阶'`。
- AND/多字段使用 `/kns8s/AdvSearch?type=expert`、`textarea.textarea-major` 与 `input.btn-search`。高级检索 UI 的 `.btn-search` 合成事件曾无效，不反复尝试相同注入。
- 当前检索框是 `#txt_search`，不是 `input[name=kw]`。
- 默认最多扫描 3 页，`--pages N` 调整，0 禁止翻页。索引命中仍须核对详情页题名及作者；索引不符回退实时检索。需要更新同一查询的候选列表时用 batch `--refresh-index`。

## 验证码、订单与权限

- `bar/verify`、拼图校验、“请依次点击”或“拖动下方拼图完成验证”：停下，让用户处理当前页；不能自动解验证。
- returnUrl 可能自动下载当前篇。恢复后先检查本次新增的作者匹配文件，不直接重新搜索。CLI 的 batch 可等回车；无交互输入时返回 2 并保留状态，用户完成后重跑。
- `bar/fee` 为机构权限外收费页，记入目录；不要把它当成等待过短。
- `bar.cnki.net` 订单生成常需 5–15 秒。下载最多等待约 40 秒，同时检查收费和验证码，不把所有等待统一改成短 sleep。
- 任务控制同一个活动标签；不要同时运行另一个浏览器任务或在等待时切换其活动标签。

## 下载归档

- CNKI 下载必须在详情页 `location.href = 链接.href`，保留 referrer；合成 `a.click()` 曾静默失败，直接 open/curl 下载链接曾报“来源应用不正确(01)”。
- CNKI 会归一化冒号、引号、破折号，所以落盘使用本次快照差异、作者后缀和时间窗口，不用完整题名硬匹配。多个新增候选不猜首条。
- `NOTFOUND`：核对作者、Chrome 下载目录和是否已下载。无关 `.crdownload` 不应阻塞已完成论文；自己的候选仍必须稳定并通过文件类型检查。
- `CNKI_DOWNLOADS_DIR` 可指定 Chrome 实际下载目录，默认 `~/Downloads`。
- 外文浏览器下载使用 `oa_dl.sh` 输出的 `DOWNLOAD_SNAPSHOT`，传给 `cnki_archive_dl.sh ... --snapshot 路径`；没有快照的旧用法只在时间窗口内存在唯一稳定 PDF 时归档。
- 内嵌 PDF 查看器要 Cmd+S → Save/OKButton，等待文件稳定后归档。只有 CAJ 时保留 CAJ 并备注。
- FAT/exFAT 的 `._*` 是 AppleDouble 伴随文件，统计时排除。跨设备使用 `shutil.move`；`os.rename` 会报 Cross-device link。若旧版本 mv 报 owner/group 权限，先核对目标文件是否到位，勿直接重下。
- 同名副本可能有不同水印，不能只用 md5 判论文身份；结合题名作者、页数和实际内容判断，页数相同本身不能证明同一篇。当前归档不覆盖同名文件。

## 注入与数据诊断

- 先查看 Chrome 实际返回的 URL/状态。JS 返回值应简单或为 JSON，不用不可靠的字符串截断判断是否已到详情页。
- shell 的 IFS 是字符集，不能用 `IFS='|||'` 分隔多字符字段；批量用 Python 参数列表。
- `WAIT_TIMEOUT` 会保留进度，不把未就绪页面记为成功。WoS 懒加载未确认完成不记入断点；会话过期时用 `--refresh` 重新检索。
- 页数脚本先查 mdls，新 PDF 常为 null，随后有限读取 PDF /Count；null 不等于坏文件，页数是辅助核验。

### 仅在结果行需要人工核对时使用的旧诊断片段

```bash
# 打开检索页后执行（EXPECT、AUTHOR 自行替换）；每页扫一次，未中则点「下一页」再来
osascript <<'EOF'
set js to "(function(){var EXPECT='题名';var AUTHOR='作者';var norm=function(s){return (s||'').replace(/[\\s:：，,。.、；;！!？?《》()（）\\-—·“”‘’\"']/g,'');};var rows=document.querySelectorAll('table tbody tr');for(var i=0;i<rows.length;i++){var t=rows[i].innerText;var a=rows[i].querySelector('a[href*=\"kcms2/article/abstract\"]');if(!a)continue;var tx=norm(a.textContent);if(tx===norm(EXPECT)&&t.indexOf(AUTHOR)>-1){location.href=a.href;return 'MATCH '+t.replace(/\\n+/g,' ').slice(0,90);}}return 'NOTHERE n='+rows.length;})()"
tell application "Google Chrome" to execute active tab of front window javascript js
EOF
```


通常优先用 `cnki_rows.js` 看结果行。确认详情页后才调用 `cnki_click.js`。
