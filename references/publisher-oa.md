# 出版社全文下载

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

只将 `%PDF-` 开头的文件作为 PDF 归档；HTML 收费页或验证页不是 PDF。网络错误、DOI 未注册、无链接及账户权限问题按实际原因记录。

出现 `needs_user` 时，请用户处理当前页面。若显示 PDF，Windows 用浏览器保存按钮或 Ctrl+S，macOS 用保存按钮或 Cmd+S，保存进配置的下载目录；完成后重跑原命令。不要假定 Agent 具有控制系统保存窗口的能力。

同一次下载快照只接受唯一且稳定的新文件；如果用户改了目录或出现多个候选，核对文献后用 `archive --file` 明确文件。不要按最新修改时间随意挑选。归档保留同名旧文件，失败或中断后先核验已有落盘再重试。
