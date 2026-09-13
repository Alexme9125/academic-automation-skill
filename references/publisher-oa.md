# 出版社全文下载

开始前沿用本任务的订阅范围回答；未说明时先问是否考虑付费/订阅，拒绝后再问放弃还是保留题录。将回答作为 `--access-policy all|free-only|free-plus-bib` 传给统一检索/下载入口。旧包装器缺少选择也会暂停，按 [人工交接](cli.md#人工交接与调度约束)补回原任务。没有免费标记不等于收费；`unclassified_rows` 须报告为待分类。

使用[统一命令行](cli.md)的 `download doi`；先从元数据取得完整 DOI。外文库/WoS 没有 CNKI 中文下载按钮，不能调用 `cnki_click.js`。

流程：doi.org 跳转 → 出版社分流 → 可公开请求的真实 PDF → 已登录浏览器页内链接 → 必要时用户保存 → 核验归档。浏览器路径复用当前会话；独立 HTTP 请求不导出用户 cookies。

| 出版社 | 策略 |
|---|---|
| Nature | 优先 articles/{id}.pdf，失败后读真实页面链接 |
| Frontiers | 尝试既有 articles / journals/education PDF 路径，失败后读页面 |
| SAGE | 在详情页内跳转 DOI PDF 下载链接 |
| Springer / Springer Nature | 详情页后转 content/pdf，内嵌查看器可能需人工保存 |
| SCIRP | 提取页面 PDF 链接 |
| OJS / 其他出版社 | 提取实际链接；article/view/{id}/{galley} 可转换为 article/download |

候选优先采用页面的 `citation_pdf_url` 或明确的正文 PDF 链接，排除 Appendix、Supplementary/Supporting Information 和 `appN.pdf` 等补充文件；JMIR 的正文 `/PDF` 不能被附录 `.pdf` 抢先选中。只有补充材料时报告“未找到正文链接”，不能计为正文已下载。

只将 `%PDF-` 开头的文件作为 PDF 归档；HTML 收费页或验证页不是 PDF。还需核对正文题名/作者及来源链接，页数仅为辅助。网络错误、DOI 未注册、无链接及账户权限问题按实际原因记录；订阅制期刊不等于当前用户无法获取该篇。

出现 `needs_user` 时，执行[人工交接](cli.md#人工交接与调度约束)：提问、等待实际回复、恢复原篇。不能仅给建议后跳去下一篇，也不能把验证未完成标成非 OA 或无权限。若显示 PDF，Windows 用浏览器保存按钮或 Ctrl+S，macOS 用保存按钮或 Cmd+S，保存进配置的下载目录。不要假定 Agent 具有控制系统保存窗口的能力。

文章页已通过验证后，程序可对同源正文链接尝试一次 `download` 属性锚点；它不能解决验证码，也不保证跨源或所有浏览器设置下都落盘。跨源链接仍用页内导航，未落盘则交给用户保存，保留标签直至当前篇解决。依据见 [MDN download 属性](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/a#download)。知网中文下载仍须使用其原有 `location.href` 流程。

同一次下载快照只接受唯一且稳定的新文件；如果用户改了目录或出现多个候选，核对文献后用 `archive --file` 明确文件。不要按最新修改时间随意挑选。归档保留同名旧文件，失败或中断后先核验已有落盘再重试。
