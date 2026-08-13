# Web of Science 流程（macOS）

用 Apple Events（`osascript` 注入 Chrome）在 Web of Science Core Collection 检索并抽题录。不走 CDP。全文路径与知网外文库相同：**题录 + DOI → `oa_dl.sh`**。WoS **没有**站内 PDF/CAJ 按钮。

先完成 SKILL.md「对话流程」：未指定网站时先问；用户已经说走 WoS 就不要再问。检索出题录后问「能下则下还是只做目录」，不要一出结果就批量 `oa_dl.sh`。

## 工作流

```bash
SK="<skill-dir>/scripts"
"$SK/wos_search.sh" '"value-added assessment"' /tmp/wos.json --pages 1
# 只要 OA 标识的子集（侧栏勾选 Open Access 再 Refine，以标题条数变化为准）：
# "$SK/wos_search.sh" '"value-added assessment"' /tmp/wos.json --oa
python3 "$SK/wos_bib.py" /tmp/wos.json wos文献清单.md --title "Web of Science 文献清单"
```

摘要页经常没有 DOI。对要下载的篇打开详情页后再抽：

```bash
# 当前标签已是 /wos/woscc/full-record/WOS:…
"$SK/macos_chrome_js.sh" "$SK/wos_full.js"
"$SK/oa_dl.sh" "<DOI>" "/目标/文件夹" "第一作者-年份-短题名"
```

英文短语同样要加引号（脚本会给多词查询自动加）。建议 Topic 检索：`"value-added assessment"`。

## 必须用 Document Search，不要用 Smart Search

| 入口 | URL | 实测 |
|---|---|---|
| **Document Search（用这个）** | `https://www.webofscience.com/wos/woscc/basic-search` | 机构 IP/代理可用时，填 `#search-option-0`（默认 Topic），点 Search，进入 `/wos/woscc/summary/{id}/relevance/1` |
| Smart Search | `…/wos/woscc/smart-search` | 检索框是 `#composeQuerySmartSearch`。提交后可能跳到 `access.clarivate.com/login`（Clarivate **个人**登录），即使机构访问已能打开检索页 |
| 顶栏「Advanced Search」 | 实际链到 `basic-search`（`#snAdvancedLink`） | 页内还有 FIELDED SEARCH / QUERY BUILDER 标签；本脚本只用默认 Topic 行 |

顶栏 Sign In / Register 是 Clarivate **个人账号**（存检索式、Marked List 同步）。机构访问另算：页脚或促销区可能出现机构标识。脚本只检测「有没有机构标识」，不要把学校名写进 skill。

## 页面结构（抽取依据）

- 结果卡片：`app-record`（内层 `.summary-record` / `.data-section`）
- 题名：`a[data-ta="summary-record-title-link"]`，链到 `/wos/woscc/full-record/WOS:…`
- 作者：`a.authors`
- 期刊：`a.summary-source-title-link`（文案常带 `arrow_drop_down`）
- 年份：`.data-section` 里单独一行的 `YYYY`（作者/会议与期刊之间），没有稳定的 year class
- 入藏号：题名 href 里的 `WOS:数字`
- DOI：摘要页只在「Full Text at Publisher」的 `KeyAID=`（DestApp=DOI）里；GetFTR 的「Free Full Text from Publisher」行通常 **没有** DOI
- OA 锁形图标：`[data-mat-icon-name="open-access"]` / `aria-label="Open Access"`
- 计数：标签标题 `"query" (Topic) – N – Web of Science Core Collection`
- 翻页：`button[aria-label="Top Next Page"]`，URL 末段 `/relevance/1` → `/relevance/2`
- 详情页全文：`a#FRLinkTa-link-0` 等，文案为 Free Full Text from Publisher / View Full Text on ProQuest / Full Text Links

## 全文怎么拿

WoS 的「Free Full Text from Publisher」走 GetFTR 网关（`/api/gateway?SrcAuth=GetFTR`）。用 `location.href = 链接.href` 可在当前标签打开，落地的是 **出版社 HTML**，不是 PDF。不要指望像知网中文库那样从 WoS 直接落盘。

正确顺序：

1. 有 DOI → `oa_dl.sh`（Nature / Frontiers 常能 curl；SAGE 需浏览器跳转且经常是 Restricted access）。
2. 摘要页无 DOI → 打开 full-record，跑 `wos_full.js`（正文常写作 `DOI10.xxxx`，中间无空格）。
3. GetFTR / ProQuest 只作备用入口；仍须在出版社页找 PDF。
4. OJS 期刊页上的「PDF」链经常是 `/article/view/{id}/{galley}`（HTML）。改成 `/article/download/{id}/{galley}` 再 curl，并用 `file` 确认。

「能下则下」= 完整 DOI 且出版社 OA/侧栏 PDF 能拿到；其余进目录并标机构订阅。「Full Text at Publisher」≠ 免费 PDF。

文献目录每条必须有发布页超链接：题名写成 `[题名](url)`，并写 `- 全文：` 或 `- 链接：`。优先 `https://doi.org/{DOI}`，否则用 WoS `/full-record/WOS:…` 或 GetFTR 落地页。禁止只写题名/作者、没有 URL。

## 注意

- **机构登录**：打开 basic-search 后若跳到 `access.clarivate.com/login` 或提示无权限，停下来让用户走图书馆代理/VPN/机构登录。不要编账号，也不要存 cookie。
- **人机验证**：标题或正文出现 captcha / robot 时停止（退出码 `2`）。
- **Cookie / Pendo**：OneTrust「Allow all」和 Pendo 问卷会挡住点击。`wos_search.sh` 会先跑 `wos_dismiss.js`。
- **虚拟列表**：不滚动时 JS 只能看到前 2～5 条有 title 的卡片，后面的 `app-record` 是空壳。脚本会 `window.scrollBy` 若干次再抽。
- **筛选**：点 Open Access 数字本身不够。必须勾选 `input[aria-label^="Open Access"]` 再点该组 **Refine**。点完核对标题里的 N 是否变了（例如 75→19）。
- **Marked List / Export**：导出 EndNote/RIS 不是全文；本流程不做批量 Export。个人未登录时 Marked List 可能不持久。
- **不要用 curl 抓 WoS HTML**，会丢会话。注入时保持 Chrome 为前置窗口。
- 不要对 WoS 详情页跑 `cnki_click.js`。

## 和知网外文库 / Scholar 怎么配合

1. WoS：入藏号、引文库收录、较完整 DOI（详情页）、OA/GetFTR 入口。
2. 知网外文库：中文平台可看到的外文题录；DOI 可能被截断。
3. Scholar：覆盖面和被引；没有 DOI 字段。
4. 三者能下的 OA 都接到 `oa_dl.sh`。
