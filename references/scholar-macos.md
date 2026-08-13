# 谷歌学术题录（macOS）

用 Apple Events（`osascript` 注入 Chrome）在 Google Scholar 检索并抽题录，写成文献目录 Markdown。不走 CDP。这是知网外文库的互补来源：Scholar 能覆盖 Sanders TVAAS 等经典文献，知网外文库往往没有。

先完成 SKILL.md「对话流程」：未指定网站/语言时先问；检索出题录后问「能下则下（侧栏 PDF/OA）还是只做目录」，不要一出结果就批量下 PDF。

## 工作流

```bash
SK="<skill-dir>/scripts"
"$SK/gs_search.sh" '"value-added assessment" education' /tmp/gs.json --pages 2
python3 "$SK/gs_bib.py" /tmp/gs.json 谷歌学术文献清单.md --title "谷歌学术文献清单"
```

可选：`--year 2015` 加 `as_ylo`（Since year）；`--pages` 最多 5，建议 1–2 页，翻太快容易出人机验证。

英文短语同样要加引号，否则 Scholar 也会拆词。

## 页面结构（抽取依据）

- 结果卡片：`.gs_r.gs_or`（内层 `.gs_ri`）
- 题名：`h3.gs_rt a`（去掉 `[PDF]` / `[HTML]` / `[CITATION]` 前缀）
- 作者/期刊/年：`.gs_a`，形如 `WL Sanders, SP Horn - Journal of …, 1998 - Springer`
- 摘要片段：`.gs_rs`（Scholar 只给 snippet，不是全文摘要）
- 被引：`.gs_fl a` 中 `Cited by N`
- 侧栏 PDF：`.gs_or_ggsm a`（常是 ResearchGate / Academia / 期刊 pdf；不一定可 curl）
- 计数：`About N results`

## 注意

- **人机验证**：标题或正文出现 `unusual traffic` / `sorry/index` 时停止，请用户在 Chrome 里点完再跑。脚本退出码 `2`。
- **不要用 curl 抓 Scholar HTML**，会缺登录态/cookie，也更容易验证码。
- Scholar **不提供 DOI 字段**。清单里先留原文链接；需要 DOI 时打开链接或用 Crossref，再接到 `oa_dl.sh`。
- 侧栏 PDF 很多是镜像，curl 可能 403；能下再用 `file` 验证，否则走机构订阅。
- 中国网络有时 `scholar.google.com` 打不开，可改 `scholar.google.com.hk`（把 `gs_search.sh` 里的主机换掉）。本次本机 `.com` 可用。
- 注入时保持 Chrome 为前置窗口。

## 和知网外文库怎么配合

1. Scholar 出题录清单（覆盖面、被引、经典文献）。
2. 知网外文库补 DOI / 中文平台可获取的篇目。
3. 有 DOI 的 OA 篇走 `oa_dl.sh`；只有 Scholar PDF 侧栏的先试链接，失败标机构订阅。
