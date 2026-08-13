# 知网外文库流程（macOS）

外文库（WWJD）详情页**没有**「PDF下载 / CAJ下载」。不要跑 `cnki_click.js`。全文只能：完整 DOI → 出版社 OA，或标注机构订阅。

驱动方式：`scripts/macos_chrome_js.sh file.js`（osascript → Chrome 前置标签）。不要用 CDP / 远程调试，本机常因 `DevToolsActivePort` 失败。

先完成 SKILL.md「对话流程」：网站/语言已确认再检索；有候选后再问「能下则下」还是「只做目录」，不要一出结果就批量 `oa_dl.sh`。

## 工作流

### 1. 检索（必须引号短语 + 点「外文」）

```bash
SK="<skill-dir>/scripts"
"$SK/cnki_foreign_search.sh" "value-added assessment" --rows
```

脚本会：给英文短语加引号（已有引号则不重复）→ 打开 `korder=SU` 检索页 → 写入 `#txt_search` → 点击 `a.en[data-val="Foreign"]` → 打印 `COUNT`。

- 退出码 `2` / `PHRASE_TOO_BROAD`：没加引号导致分词爆炸。改用 `"value-added assessment"` 这种短语，不要把单词拆开。
- 退出码 `1` / `ZERO`：缩短短语、去掉过窄限定，或换同义短语再检。
- **点任何筛选后必须再跑计数**。`cnki_count.js` 的 `n` 与点击前相同 = 未生效。学科类目尤其不可靠，不要当成已过滤。
- 侧栏「来源类别」（Scopus / SSCI / EI）可以点，同样以计数变化为准。
- 结果混杂时，在当前检索页跑 `cnki_edu_filter.js` 先收教育相关行（按词边界匹配 education/student/teacher/school/vocational 等，不用 assessment/science 子串）。

建议短语：`"value-added assessment"`、`"value-added evaluation"`、`"science education assessment"`。

翻页：当前页扫完再点「下一页」，每页用 `cnki_rows.js` 抽 `title` + `href`。

### 2. 挑选后批量抽题录

把选中的 `kcms2/article/abstract` 链接写入 `urls.txt`（一行一个），然后：

```bash
"$SK/cnki_metaloop.sh" urls.txt meta.json
python3 "$SK/cnki_bib.py" meta.json 权威外文文献清单.md --title "外文文献清单"
```

`cnki_meta.js` 会取**最长 DOI**（含 `(09).12` 这类括号段），避免信知网头部的截断 DOI。可疑时再对当前详情页跑 `cnki_full_doi.js`。

清单每条必须含发布页超链接：题名写成 `[题名](url)`，并另写 `- 全文：` 或 `- 链接：`。优先 `https://doi.org/{DOI}`；无 DOI 时用知网 `kcms2/article/abstract` 摘要页。下载成功后把全文行改成 OA 或机构订阅。禁止只写题名/作者、没有 URL。

### 3. 按 DOI 取全文

先确认 DOI 完整，再：

```bash
"$SK/oa_dl.sh" "10.1177/21582440251382664" "/目标/文件夹" "chen-et-al-2025-value-added-assessment"
```

| 退出码 | 含义 | 接着做什么 |
|---|---|---|
| 0 | curl 已归档 | `file` / `PAGES:` 已打印；把清单该条标为 OA |
| 2 | `DOI_UNREGISTERED` | 出版社未注册该 DOI，只保留题录，不要死磕 curl |
| 3 | `NEED_BROWSER jump` | 已页内跳转，等 ~/Downloads 出现 PDF，再 `cnki_archive_dl.sh` |
| 3 | `NEED_BROWSER save-dialog` | 内嵌 PDF 查看器：Computer Use 发 Cmd+S，点 Save（辅助功能树里常是 Save / OKButton），再归档 |
| 3/4 | `NEED_BROWSER find-link` | 当前页跑 `pub/find_pdf.js`（或对应 `pub/*.js`），找到链接后 curl；不是 PDF 就改浏览器跳转 |

站点分流与实测策略见 [publisher-oa.md](publisher-oa.md)。

归档文件名建议：`{第一作者}-et-al-{简短主题}-{期刊简称}.pdf`。

### 4. 核验与汇报

- 统计时排除 `._*.pdf`。
- 页数用 `scripts/pdf_pages.py`（mdls 对新文件常为 null，脚本会解析 PDF `/Count`）。
- exFAT 上 `mv` 报 owner/group 权限可忽略，用 `ls` 确认文件在。
- 向用户汇报：题录 N 篇、OA 全文 N 篇、机构订阅/DOI 未注册清单。

## 不要做的事

- 对外文详情页使用 `cnki_dl.sh` / `cnki_click.js`。
- 用 `?rlang=FOREIGN` 代替点击「外文」。
- 英文多词检索不加引号。
- 信知网头部短 DOI 去 curl（先补全）。
- 把 curl 下来的 HTML/XML 当 PDF 归档（必须 `file`）。
- 点击筛选后不核对「共找到 N 条」。
- 外文检索之后直接用中文题名检索却不点回「中文」。语言标签会保留，外文库里搜中文题名会显示「暂无数据」，容易误判成限流。`cnki_dl.sh` 已自动点回中文。
