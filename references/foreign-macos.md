# 知网外文库流程（站点细节）

开始前沿用本任务的订阅范围回答；未说明时先问是否考虑付费/订阅，拒绝后再问放弃还是保留题录。将回答作为 `--access-policy all|free-only|free-plus-bib` 传给统一检索/下载入口。旧包装器缺少选择也会暂停，按 [人工交接](cli.md#人工交接与调度约束)补回原任务。没有免费标记不等于收费；`unclassified_rows` 须报告为待分类。

> 新版优先使用[统一命令行](cli.md)。下列 `.sh` 示例仅为 macOS 兼容入口；Windows 使用对应的统一命令。站点选择器与匹配规则两平台共用，退出状态以新版 CLI 文档为准。

外文库（WWJD）详情页**没有**「PDF下载 / CAJ下载」。不要跑 `cnki_click.js`。全文走完整 DOI → 出版社实际可用链接或已登录浏览器；根据该篇实际返回区分成功、待人工、链接故障和已证实的权限不足。

驱动方式以[统一命令行](cli.md)为准：Windows 使用扩展，macOS 可用 Apple Events。不要另开默认配置的远程调试进程或重建登录态。

先完成 [入口](../SKILL.md)的「对话流程」：网站/语言已确认再检索；交付方式未明确时，在有候选后再问「能下则下」还是「只做目录」。用户已经要求下载或只做目录时不重复询问，直接按已授权范围执行。

## 工作流

### 1. 检索（必须引号短语 + 点「外文」）

```bash
SK="<skill-dir>/scripts"
"$SK/cnki_foreign_search.sh" "value-added assessment" --rows
```

脚本会：给英文短语加引号（已有引号则不重复）→ 打开 `korder=SU` 检索页 → 写入 `#txt_search` → 点击 `a.en[data-val="Foreign"]` → 返回实际总数与当前页提取数。

- 退出码 `64` / `PHRASE_TOO_BROAD`：没加引号导致分词爆炸。改用 `"value-added assessment"` 这种短语，不要把单词拆开。
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

目录格式遵循[入口](../SKILL.md)。本模式优先完整 DOI，缺 DOI 则使用知网摘要页；实际下载后更新全文状态。

### 3. 按 DOI 取全文

先确认 DOI 完整，再：

```bash
"$SK/oa_dl.sh" "10.1177/21582440251382664" "/目标/文件夹" "chen-et-al-2025-value-added-assessment"
```

新流程使用 `download doi`，退出 0 后核对 `result.path`；退出 2 按[人工交接](cli.md#人工交接与调度约束)等待回复；退出 3 表示未找到链接、来源页失效或 DOI 未注册，查看 message。旧 `oa_dl.sh` 也保留退出码 2，不再与退出码 3 混用；Agent 应使用统一入口的 JSON 状态。

站点分流与实测策略见 [publisher-oa.md](publisher-oa.md)。

归档文件名建议：`{第一作者}-et-al-{简短主题}-{期刊简称}.pdf`。

### 4. 核验与汇报

- 统计时排除 `._*.pdf`。
- 页数用 `scripts/pdf_pages.py`（mdls 对新文件常为 null，脚本会解析 PDF `/Count`）。
- 归档使用排他创建与复制，核验后才删除源文件；任何失败先检查实际文件，不直接重下。
- 向用户汇报：题录数、已核验正文数，以及待人工、用户跳过、已证实无法获取和链接/网络故障清单；不要把失败一律归为机构订阅。

## 不要做的事

- 对外文详情页使用 `cnki_dl.sh` / `cnki_click.js`。
- 用 `?rlang=FOREIGN` 代替点击「外文」。
- 英文多词检索不加引号。
- 信知网头部短 DOI 去 curl（先补全）。
- 把 curl 下来的 HTML/XML 当 PDF 归档（必须 `file`）。
- 点击筛选后不核对「共找到 N 条」。
- 外文检索之后直接用中文题名检索却不点回「中文」。语言标签会保留，外文库里搜中文题名会显示「暂无数据」，容易误判成限流。`cnki_dl.sh` 已自动点回中文。

## 进度与恢复

`cnki_metaloop.sh` 的输出旁以 `.progress.json` 保存已完成 URL。相同输入重跑复用已有题录，追加 `--refresh` 重新提取；不要把部分结果当作完整结果。遇验证先让用户处理 Chrome 当前页，再用原命令续跑。`cnki_foreign_search.sh` 每次重新检索并提取当前页，不提供该缓存选项。

摘要页出现 `PAGE_NOT_FOUND` 时，程序保留已完成记录和 `failed_url`，先回检索结果重新取得同一篇的链接，核对题名/作者或 DOI 后恢复。用户指定的篇目不能自行替换；仅指定方向、由 Agent 选篇的任务可以在原范围内补选，但应保留失效记录并说明替换。DOI 比较长度前去除已识别的追踪参数，保留括号等 DOI 本身的字符。
