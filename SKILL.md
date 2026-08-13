---
name: cnki-download
description: 按用户给出的文献方向，在知网中文库/外文库、Web of Science 或谷歌学术检索，再按用户选择下载能获取的全文或只整理题录目录。当用户要求从知网下载文献、CNKI、外文文献、WWJD、Web of Science、WoS、WOS、谷歌学术、Google Scholar、按 DOI 下 PDF、整理文献目录、把目录里的文献下下来时使用。未说明网站、语言或交付方式时先问再做。macOS 版依赖已登录的 Chrome 与 AppleScript（osascript）。
version: 1.4.1
---

# CNKI 文献批量下载与归档（macOS）

先判断任务走哪条流程，再读对应章节：

| 模式 | 判断 | 走哪里 |
|---|---|---|
| **中文库** | 中文期刊/博硕/会议，详情页有「PDF下载 / CAJ下载」 | 下文「中文库」；脚本 `scripts/cnki_dl.sh` |
| **外文库** | 英文检索、WWJD、外文期刊/会议，详情页只有 DOI、**没有** PDF/CAJ 按钮 | 读 [references/foreign-macos.md](references/foreign-macos.md)。**禁止**对此外文详情页跑 `cnki_click.js` |
| **Web of Science** | WoS / WOS / Core Collection / Clarivate | 读 [references/wos-macos.md](references/wos-macos.md)；脚本 `wos_search.sh` + `wos_bib.py`。站内无 PDF，全文走 DOI + `oa_dl.sh` |
| **谷歌学术** | Google Scholar 检索、出文献目录 md、补经典外文题录 | 读 [references/scholar-macos.md](references/scholar-macos.md)；脚本 `gs_search.sh` + `gs_bib.py` |

本文件是 **macOS** 版：用 `osascript` 驱动已登录的 Google Chrome 执行 JS。CNKI 场景下不要依赖 Chrome 远程调试 / CDP（本机常因 `DevToolsActivePort` 权限失败）；osascript 更省事。Windows 版另计，不要把这里的 `osascript` / `open -a` 直接搬过去。

## 前提条件

1. **macOS + Google Chrome**，且已在知网登录机构/个人账号。验证：`open -a "Google Chrome" https://www.cnki.net/`，页头显示机构名即已登录；若只显示「个人登录」，请用户先登录。Web of Science 用同一 Chrome 会话：能打开 `https://www.webofscience.com/wos/woscc/basic-search` 即可；若跳到 `access.clarivate.com/login`，请用户走图书馆代理/VPN。顶栏 Sign In 是 Clarivate 个人账号，与机构访问不是一回事。
2. **AppleScript 可驱动 Chrome 执行 JS**。验证：
   ```bash
   osascript -e 'tell application "Google Chrome" to execute active tab of front window javascript "document.title"'
   ```
   若报 `JavaScript from Apple Events is disabled`，请用户在 Chrome 菜单 View → Developer → 勾选 Allow JavaScript from Apple Events。
3. 注入 JS 时保持 Chrome 为前置窗口（脚本针对 `front window` 的活动标签）。
4. 用户提供：文献清单（题名+第一作者）、各篇归属文件夹。若清单是目录文件（md/html），先解析成 `题名|第一作者|目标文件夹` 列表。外文任务则需要主题词/英文短语和归档根目录。

共享注入：`scripts/macos_chrome_js.sh /path/to/file.js`。

---

## 对话流程（先问再做）

主路径是：**方向 →（必要时）问网站和语言 → 检索 → 问交付方式 → 执行 → 汇报**。用户已经说清的项不要再问。

### 入口

| 用户已给出的 | 怎么走 |
|---|---|
| 现成题名清单（要逐篇下全文） | 不问网站。中文题名走中文库，英文题名走外文库/出版社。仍可问归档文件夹（若未给）。 |
| 只有研究方向（如「教学评价」「科学教育」） | 先确认网站和语言，再检索。 |

### 问 1：网站和语言（检索前）

方向有了，但网站或语言未提及时，一次问清这两项，**等回答后再打开检索页**：

1. 在哪个网站搜？知网中文库 / 知网外文库 / Web of Science / 谷歌学术 / 几个都要  
2. 要哪种语言？中文 / 英文 / 中英都要  

对应关系：中文 → 知网中文库；英文 → 知网外文库、Web of Science 或谷歌学术（用户选）；中英都要 → 分两次检索，中文任务前点回「中文」标签。用户已写「从知网下中文」「用 WoS」或「用谷歌学术」就直接开搜。

### 检索

按选定网站执行（中文库 / 外文库 / WoS / Scholar，见后文）。检索结束后用几句话汇报：命中大约多少条、本页抽了几条、和主题是否对得上。不要在这一步开始批量下载。

### 问 2：交付方式（检索后、下载前）

有候选结果后，问用户要哪一种（已吩咐则跳过）：

- **能下则下**：把能获取的全文下载归档；下不了的（无链接、非 OA、需订阅、DOI 未注册）全部写入文献目录，并标注原因  
- **只做目录**：所有命中都只整理成 Markdown 目录，不下载 PDF/CAJ  

外文库和 Web of Science 都没有站内 PDF 按钮，「能下则下」= 有完整 DOI 且出版社 OA/侧栏 PDF 能拿到的才下，其余进目录并标机构订阅。

**文献目录必须带发布页链接。** 凡写成 Markdown 文献目录（只做目录，或「能下则下」里下不了的题录），**每一条都必须有指向该文献发布页面的可点击超链接**，不能只有题名和作者。题名写成 `[题名](url)`，并另写 `- 链接：` 或 `- 全文：` 行。URL 优先顺序：出版社落地页 / `https://doi.org/{DOI}` → 知网 `kcms2/article/abstract` 摘要页 → Scholar 题名 href → WoS `/full-record/WOS:…` → 侧栏 PDF。没有 DOI 时用当时最好的 URL，并注明来源。禁止输出无 URL 的目录条目。

示例：

```markdown
### 1
**[Value-added assessment in science education](https://doi.org/10.1177/21582440251382664)**
- 作者：Chen, L.
- 期刊：SAGE Open, 2025
- DOI：10.1177/21582440251382664
- 链接：https://doi.org/10.1177/21582440251382664
```

中文库目录用知网摘要页，例如 `**[题名](https://kns.cnki.net/kcms2/article/abstract?…)**` 加 `- 链接：` 同一 URL。

### 执行与完成

按选定方式跑对应脚本，收尾核验后汇报：目录路径、成功下载 N 篇、仅题录 N 篇、失败/待人工清单。验证码、人机验证仍须停下来交给用户。

---

## 中文库

### 核心规则（血泪教训，务必遵守）

1. **触发下载必须用 `location.href = 链接.href` 页内跳转**。JS 合成 `a.click()` 会被知网拦截（无下载、无新标签）；`isTrusted` 事件无法伪造。
2. **禁止直接打开下载链接**（`open`/curl `bar.cnki.net/bar/download/order?...`）——会报「来源应用不正确(01)」，必须携带详情页 referrer 页内跳转。
3. **下载文件名由知网归一化**：全角冒号 `：`→`_`、破折号 `——`→`-`、弯引号可能变化。所以**按 `*_第一作者.pdf` 后缀 + 最近修改时间**匹配新下载文件，不要用完整题名匹配。
4. **人名不能当主题词检索**（题名字段只匹配题名），会得 0 条。
5. **验证码**：连续下载约 10~20 篇后，下载会跳转到 `bar.cnki.net/bar/verify` 的「请依次点击：X X X」文字点选验证（参数 `rb=EveryNTimes`）。**无法自动通过**——把页面呈现给用户，请用户按顺序点字并点「确定」；通过后 returnUrl 会自动继续该篇下载。用户确认后按 `_作者` 后缀检查文件是否落盘。
6. **语言库会跨检索保留**。点过「外文」后，新打开的检索页仍停在外文库；用中文题名去搜会显示「抱歉，暂无数据，请稍后重试」。这**不是限流**。`cnki_dl.sh` 打开检索页后会先点 `a.ch[data-val="Chinese"]`。若已在中文库仍暂无数据，再怀疑检索式或限流（等 60–180 秒）。
7. **节奏**：页面跳转 sleep 2–3 秒即可（本机网络好），不要过长等待；每篇之间可再留 2–4 秒以降低触发验证码频率。
8. 外接硬盘（FAT/exFAT）会产生 `._*` AppleDouble 伴随文件，统计 PDF 数量时排除它们。`mv` 到 exFAT 可能报 `set owner/group ... Operation not permitted`，**文件通常已经移动成功**，用 `ls` 确认即可，不要当成失败重下。
9. 若要在已打开的检索页改关键词，检索框是 `#txt_search`（class `search-input`），不是 `input[name=kw]`。

### 工作流

从研究方向检索进来时，先完成上文「问 2：交付方式」。用户选「只做目录」则抽题录写 Markdown（`cnki_rows.js` 的 `href` 即 kcms2 摘要页，每条必须写成 `[题名](href)` 并加 `- 链接：`），不要跑 `cnki_dl.sh`。选「能下则下」或直接丢来题名清单时，再按下面逐篇下载。

#### 1. 准备状态清单（可选但推荐）

建立 `下载状态.md`，按主题分组，每行：`| ⏳ | 题名 | 第一作者 | 编号 | 备注 |`，图例：✅ 已下载 / ⏳ 待下载 / ♻️ 已有全文 / ❌ 失败 / ⚠️ 需人工。已有全文的条目直接标 ♻️ 并备注路径。

#### 2. 逐篇下载（主脚本）

```bash
/path/to/skills/cnki-download/scripts/cnki_dl.sh "检索题名" "第一作者" "/目标/文件夹"
```

脚本行为：打开检索页 → 归一化题名精确/包含匹配（自动跳转详情页）→ 点 PDF下载（无则 CAJ下载）→ 轮询 ~/Downloads，等到 `Unconfirmed *.crdownload` 消失后再按 `*_作者.pdf|caj` 归档（Chrome 落盘常要 10 秒以上，固定 sleep 会误判失败）。
退出码：`0` 成功；`1` 无结果/未匹配/空库（先确认语言标签在「中文」）；`2` 验证码（转人工）；`3` 详情页无下载链接；`4` 文件未落盘；`64` 参数错误。
stdout 的 `SEARCH[...]:` 行包含匹配到的结果行信息（题名/作者/期刊），用于人工核对是否下对文章。

每成功一篇，更新状态清单：

```bash
python3 /path/to/skills/cnki-download/scripts/cnki_status.py "题名(可只给片段)" "✅" "2026-08-07 已下载" "/path/to/下载状态.md"
```

#### 3. 特殊情形处理

**A. 检索命中多条、首条不是目标文章（NOMATCH 或匹配到相似题名）**
用「题名精确 + 作者行校验 + 翻页」定位：

```bash
# 打开检索页后执行（EXPECT、AUTHOR 自行替换）；每页扫一次，未中则点「下一页」再来
osascript <<'EOF'
set js to "(function(){var EXPECT='题名';var AUTHOR='作者';var norm=function(s){return (s||'').replace(/[\\s:：，,。.、；;！!？?《》()（）\\-—·“”‘’\"']/g,'');};var rows=document.querySelectorAll('table tbody tr');for(var i=0;i<rows.length;i++){var t=rows[i].innerText;var a=rows[i].querySelector('a[href*=\"kcms2/article/abstract\"]');if(!a)continue;var tx=norm(a.textContent);if(tx===norm(EXPECT)&&t.indexOf(AUTHOR)>-1){location.href=a.href;return 'MATCH '+t.replace(/\\n+/g,' ').slice(0,90);}}return 'NOTHERE n='+rows.length;})()"
tell application "Google Chrome" to execute active tab of front window javascript js
EOF
```

翻到后接 `scripts/cnki_click.js` 下载。**相似题名陷阱**：如《…的应用》与《…的应用策略》是两篇不同文章，务必用行内作者名校验，下完看文件名确认。

**B. 验证码（退出码 2 或页面标题为「拼图校验-中国知网」）**
告知用户当前标签页显示验证，请其按提示顺序点字并确定；等待用户回复后，按 `*_作者` 后缀在 ~/Downloads 检查该篇是否已落盘，落盘则归档继续。

**C. 题名含特殊符号导致 0 结果**
去掉 `《》〈〉""` 等符号或截取题目前半段（「——」之前）重检；仍失败则在清单标 ⚠️ 待人工。

**D. 只有 CAJ 下载**
脚本自动下载 .caj 并归档，备注「CAJ格式」（阅读需 CAJViewer，用户可能更想要 PDF，可提示）。

#### 4. 收尾核验

```bash
# 逐个文件夹点数（排除 ._ 伴随文件与目录文件）
# 新下载的 PDF 用 mdls 常得到 null，优先用脚本回退解析 /Count
python3 /path/to/skills/cnki-download/scripts/pdf_pages.py "文件.pdf"
```

- 同名文件重复出现时（并行进程/重复下载）：知网每次下载的字节可能不同（水印），**用页数而非 md5 判断是否同一篇**；确认归档版有效后，把多余副本移入废纸篓（`mv ~/.Trash/`，勿 rm）。
- 更新状态清单汇总数字；向用户汇报：成功 N 篇、CAJ N 篇、失败/待人工清单。

### 易错点清单

- 用 `a.click()` 或直接 `open` 下载链接 → 静默失败 / 「来源应用不正确」。
- 用完整题名匹配下载文件 → 因符号归一化而漏判；用 `_作者` 后缀。
- 把作者名塞进主题检索 → 0 结果。
- 相似题名取首条 → 下错文章；必须校验作者行。
- 精确匹配只在第 1 页找 → 漏掉排后面的目标；要翻页。
- 统计时把 `._xxx.pdf` 算进去 → 数量翻倍。
- sleep 过长拖慢整体；验证码出现却硬闯 → 反复失败。
- 外文检索后不点回「中文」就搜中文题名 → 「暂无数据」，误当成限流。

---

## 外文库（摘要）

外文库只给题录 + 摘要 + DOI，**没有**知网全文下载。正确产物是「带发布页超链接的题录清单 + OA PDF（能下的）+ 机构订阅标注（下不了的）」，不是对知网点 PDF下载。`cnki_bib.py` 会把题名链到 `https://doi.org/{DOI}` 或知网摘要页。

硬约束（细节与命令见 [references/foreign-macos.md](references/foreign-macos.md)，出版社分流见 [references/publisher-oa.md](references/publisher-oa.md)）：

1. 英文短语必须加引号，否则分词爆炸（`value-added assessment` 无引号可到上百万条无关结果）。用 `scripts/cnki_foreign_search.sh "短语"`。
2. 「外文」是客户端过滤：点 `<a class="en" data-val="Foreign">`，`?rlang=FOREIGN` 无效。点完必须再读「共找到 N 条」；计数不变 = 点击未生效。不要依赖「学科」筛选（常点了计数不变）。
3. 知网头部 DOI 常截断（`10.53469/JRVE.2025.7` 实际是 `…7(09).12`）。以 `cnki_meta.js` / `cnki_full_doi.js` 的**最长候选**为准，再解析 `https://doi.org/{DOI}`。
4. 全文绕道出版社：`scripts/oa_dl.sh <DOI> <文件夹> [文件名]`。curl 被反爬（SAGE 403、Springer HTML）时改浏览器；Springer 内嵌 PDF 查看器用 Computer Use：Cmd+S → Save。
5. curl 或落盘后必须 `file` 确认是 PDF，再用 `mdls` 看页数（个别 PDF 页数元数据为 null，以 `file` 为准）。

建议检索式（均带引号）：`"value-added assessment"`、`"value-added evaluation"`、`"science education assessment"`。侧栏「来源类别」有 Scopus/SSCI/EI 计数，可点，但点后同样要核对条数变化。

---

## Web of Science（摘要）

用同一套 `osascript` 注入 Chrome，在 Core Collection 的 **Document Search**（`/wos/woscc/basic-search`）做 Topic 检索并抽题录。不要用 Smart Search（提交后可能跳到 Clarivate 个人登录页）。WoS 只给题录 + 入藏号 + 出版社/GetFTR 链接，**没有**站内 PDF；全文与外文库一样走 DOI → `oa_dl.sh`。摘要页 DOI 常缺失，要下的篇再开 `/full-record/WOS:…` 跑 `wos_full.js`。目录条目优先链到 `https://doi.org/{DOI}`，否则用 full-record URL。细节见 [references/wos-macos.md](references/wos-macos.md)。

```bash
SK="<skill-dir>/scripts"
"$SK/wos_search.sh" '"value-added assessment"' /tmp/wos.json --pages 1
python3 "$SK/wos_bib.py" /tmp/wos.json wos文献清单.md --title "Web of Science 文献清单"
```

机构未登录或跳出 `access.clarivate.com/login` 时停下来让用户走图书馆代理/VPN，不要编账号。结果列表是懒加载，不滚动只能抽到前几条。

---

## 谷歌学术（摘要）

用同一套 `osascript` 注入 Chrome，在 scholar.google.com 抽题录并写成 Markdown。英文短语同样加引号；一次取 1–2 页，出现 `unusual traffic` 就停下来让用户点验证。Scholar 没有 DOI 字段，清单里必须留下原文 href（题名超链接 + `- 链接：`）；无 href 时用侧栏 PDF 兜底。细节见 [references/scholar-macos.md](references/scholar-macos.md)。

```bash
SK="<skill-dir>/scripts"
"$SK/gs_search.sh" '"value-added assessment" education' /tmp/gs.json --pages 2
python3 "$SK/gs_bib.py" /tmp/gs.json 谷歌学术文献清单.md --title "谷歌学术文献清单"
```

---

## 脚本清单

中文库（保持原流程）：

- `scripts/cnki_dl.sh` —— 单篇下载（打开检索页→点回「中文」→匹配→详情页→PDF/CAJ→等待 crdownload 结束→归档）
- `scripts/cnki_chinese.js` —— 点「中文」标签（`a.ch[data-val="Chinese"]`）
- `scripts/cnki_click.js` —— 详情页触发 PDF/CAJ（`location.href`，含验证码检测）
- `scripts/cnki_status.py` —— 状态清单行更新
- `scripts/pdf_pages.py` —— PDF 页数（mdls 为空时解析 /Count）

外文库 / 共用：

- `scripts/macos_chrome_js.sh` —— 把 JS 注入 Chrome 前置标签
- `scripts/cnki_foreign_search.sh` —— 引号短语检索 + 点「外文」+ 打印计数（`--rows` 抽出本页）
- `scripts/cnki_foreign.js` / `cnki_count.js` / `cnki_rows.js` / `cnki_edu_filter.js`
- `scripts/cnki_meta.js` / `cnki_full_doi.js` / `cnki_metaloop.sh` / `cnki_bib.py`
- `scripts/oa_dl.sh` / `cnki_archive_dl.sh` / `scripts/pub/*.js`
- `scripts/gs_search.sh` / `gs_rows.js` / `gs_bib.py` —— 谷歌学术检索 + 题录 Markdown
- `scripts/wos_search.sh` / `wos_rows.js` / `wos_full.js` / `wos_bib.py` —— Web of Science 检索 + 详情 DOI + 题录 Markdown（`wos_oa.js` / `wos_scroll.js` / `wos_next.js` / `wos_status.js` / `wos_dismiss.js`）
