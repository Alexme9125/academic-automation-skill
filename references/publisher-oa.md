# 出版社全文下载

开始前沿用本任务的订阅范围回答；未说明时先问是否考虑付费/订阅，拒绝后再问放弃还是保留题录。将回答作为 `--access-policy all|free-only|free-plus-bib` 传给统一检索/下载入口。旧包装器缺少选择也会暂停，按 [人工交接](cli.md#人工交接与调度约束)补回原任务。没有免费标记不等于收费；`unclassified_rows` 须报告为待分类。

使用[统一命令行](cli.md)的 `download doi`；先从元数据取得完整 DOI。外文库/WoS 没有 CNKI 中文下载按钮，不能调用 `cnki_click.js`。

流程：doi.org 跳转 → 出版社分流 → 可公开请求的真实 PDF → 已登录浏览器页内链接 → macOS 两种后端尝试原生保存 → 必要时用户保存 → 核验归档。浏览器路径复用当前会话；独立 HTTP 请求不导出用户 cookies。

| 出版社 | 策略 |
|---|---|
| Nature | 优先 articles/{id}.pdf，失败后读真实页面链接 |
| Frontiers | 尝试既有 articles / journals/education PDF 路径，失败后读页面 |
| SAGE | 在详情页内跳转 DOI PDF 下载链接 |
| Springer / Springer Nature | 详情页后转 content/pdf，内嵌查看器可能需人工保存 |
| SCIRP | 提取页面 PDF 链接 |
| OJS / 其他出版社 | 提取实际链接；article/view/{id}/{galley} 可转换为 article/download |

候选优先采用页面的 `citation_pdf_url` 或明确的正文 PDF 链接，排除 Appendix、Supplementary/Supporting Information 和 `appN.pdf` 等补充文件；JMIR 的正文 `/PDF` 不能被附录 `.pdf` 抢先选中。只有补充材料时报告“未找到正文链接”，不能计为正文已下载。

直接 HTTP 下载同时核对响应状态、声明长度、实际字节数和 PDF 尾部结构；安装 `pypdf` 时还检查可解析性。传输不足最多重取一次，失败保留 `.part` 和 `.http.json` 诊断，再进入现有浏览器来源。拒绝 HTML、未请求的部分响应和不完整 PDF，不能只看 `%PDF-` 标头。还需核对正文题名/作者及来源链接，页数仅为辅助。网络错误、DOI 未注册、无链接及账户权限问题按实际原因记录；订阅制期刊不等于当前用户无法获取该篇。

出现 `needs_user` 时，执行[人工交接](cli.md#人工交接与调度约束)：提问、等待实际回复、恢复原篇。不能仅给建议后跳去下一篇，也不能把验证未完成标成非 OA 或无权限。若需人工保存，用户可用浏览器下载按钮保存进返回的 `save_folder` 或配置的下载目录；明确其他文件位置时用 `archive --file`。不能另写未经窗口识别的快捷键脚本绕过暂停。

macOS 两种后端的原生保存需要 [辅助功能权限](install-macos.md)，并要求绑定 PDF 仍为 Chrome 当前标签。它同时核对按钮文字和查看器控件，避免把共用控件 ID 的 Google Drive 按钮当成“下载”；确认保存窗口、目标文件名和目录后才点击“存储”。除了原 PDF 地址，目前还接受已实测的 Oxford → Silverchair 重定向，并要求 PDF 文件名一致；其他地址变化交给用户核对。程序保留原始来源，临时地址参数不写入检查点。动作不确定时不重复点击；重跑优先核验已有文件。Chrome 自身的 AppleScript `save tab` 在本机 PDF 测试中保存了 HTML 包装页，因此不采用该命令获取正文。

文章页已通过验证后，Apple Events 可对同源正文链接尝试一次 `download` 属性锚点；它不能解决验证码，也不保证跨源或所有浏览器设置下都落盘。跨源链接仍用页内导航，未落盘时按上述原生保存或人工交接处理，保留标签直至当前篇解决。依据见 [MDN download 属性](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/a#download)及 [Apple UI scripting](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/AutomatetheUserInterface.html)。知网中文在 Apple Events 下保留 `location.href`，扩展下使用站点原有按钮的真实点击；两者都保留详情页来源。

同一次下载快照只接受唯一且稳定的新文件；如果用户改了目录或出现多个候选，核对文献后用 `archive --file` 明确文件。不要按最新修改时间随意挑选。归档保留同名旧文件，失败或中断后先核验已有落盘再重试。

扩展后端在点击前将绑定任务标签置前台，先检查验证、Cookie 遮罩及控件是否可操作；这些预检不触发下载。收到 `needs_consent` 时由用户选择 Cookie 设置，不能强制点击底层控件。

已发起正文请求时保存 `publisher_stage`。用户验证后恢复，先检查文件，再读取当前页及同篇弹出页；同篇 PDF 已打开则继续保存，不返回文章页重复点击。扩展在 macOS 保存前会将 Playwright 绑定页面与 Chrome 原生窗口、标签和 PDF URL 对齐，再使用受控保存窗口流程；Windows 的查看器保存继续由用户处理。两端均保留目录恢复，不把缺少下载事件当成重点击授权。
