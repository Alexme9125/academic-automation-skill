> **重要权限与安全提示：本 Skill 会让 Agent/Harness 在执行 macOS 界面自动化和 PDF 原生保存时，向你索要系统无障碍（辅助功能）权限，以及控制 Chrome / System Events 的自动化权限。无障碍权限允许应用控制系统界面，授权范围不限于单个网页。若有任何安全顾虑，请勿使用本 Skill，也不要授予相关权限。**
>
> **此提示在 Windows 和 macOS 两个包的中英文 README 中均以普通字号加粗保留。Windows 当前通过 Playwright 扩展操作网页，系统保存窗口由用户处理；请审慎判断所用 Agent/Harness 请求的额外系统控制权限。**
>
> **Accessibility and safety: macOS UI automation will ask your Agent/Harness to obtain system Accessibility and automation permissions. If you have security concerns, DO NOT USE THIS SKILL or grant these permissions. Windows currently leaves system Save dialogs to the user.**

# v2.0.0-beta.4：PubMed、下载核验与平台使用规则

Beta 4 以 PubMed 适配与下载测试为基础，将官方题录接口、文件完整性检查和人工交接结合，补充从检索到归档的核验依据。此前测试中，部分 PDF 未完整接收却被记为下载成功，重新运行后又被缓存跳过；本版在首次归档和续跑时共用检查，发现损坏则保留文件并暂停，避免把已有路径直接视为合格全文。

本版继续作为 **Pre-Release** 分发，面向能执行本地命令的 Coding Agents。macOS 的 Skill 流程仅使用 Apple Events，原生保存使用 System Events；Windows 使用 Playwright 官方扩展。两端共享 Python 核心，实际网站与模型行为的验收分别记录。

## 本版变化

| 内容 | Beta 4 的处理 |
|---|---|
| PubMed 检索与题录 | 使用 NCBI 官方接口检索、分页和补齐元数据，支持 PMID / PubMed URL；按 PMID 去重并保存进度，勘误等关联记录单独保留 |
| PubMed 全文与续跑 | 优先使用 PMC 现行公开 HTTPS 数据服务，核对正文版本；没有可用正文 PDF 时转同篇出版社入口，支持单篇、批量与题录目录 |
| 订阅范围确认 | PubMed、知网外文、WoS 和 Scholar 检索前确认是否考虑订阅；拒绝后再确认放弃还是保留题录，同一任务沿用回答，不能自动购买 |
| 不完整 PDF 与旧缓存 | 核对同一次 HTTP 响应的长度和实际字节数，检查 PDF 结构；有界重试后仍失败则保留诊断。旧缓存重新核验，损坏文件不会被再次采用，也不覆盖原件 |
| 知网文件兼容 | 识别实测出现的 WebFastLoad 尾部格式，保留原始字节；继续保留题名、作者及详情页来源核对 |
| 连接及下载状态 | Windows 新建扩展连接前要求 Token，内部连接页不算已验证的普通网页；检查后台与遮罩状态，缺少下载事件时先查目录，不能追加不确定的点击 |
| 人工交接 | Skill 在查看器自动保存受阻后询问“仅题录”或“保留标签页、批量手动下载”，等实际选择再调整交付；待手动与已归档分别统计 |

“已归档”表示文件已保存并通过当时可用的核验；“正文自动核验”还要求能解析 PDF，并核对首页题名和作者。`pypdf` 是可选依赖，未安装或无法提取文字时须标记“正文未自动核验”；已安装解析器发现文件无法解析，或明确发现错篇、附录时，不能计为合格正文。没有完成身份核验，可能遗漏正文与附录混淆或题名作者不符。

## 平台与权限

| 使用方式 | 环境要求 | 浏览器和保存方式 |
|---|---|---|
| 纯 PubMed 接口、题录及 PMC 公开文件 | Python 3.9+ 与网络；`pypdf` 可选 | 不要求 Chrome、Node.js、扩展或系统无障碍权限 |
| macOS 浏览器流程 | Python 3.9+、日常 Chrome；启用 Allow JavaScript from Apple Events | **仅使用 Apple Events，不使用 Playwright，也不因失败切换为扩展。** 原生保存需要上方强调的辅助功能及自动化权限 |
| Windows 浏览器流程 | Python 3.9+、Node.js 22+、日常 Chrome、锁定的 Playwright CLI 0.1.19 | **需要官方扩展，并在新连接前提供 Token。** 查看器自动保存尚不能保证稳定，系统保存窗口由用户处理 |

macOS 的原生保存会识别 Chrome 内置 PDF 查看器及标准保存窗口，核对当前篇、文件名和目录后再操作；出现未知窗口或权限不足便暂停。用户拒绝授权时停止该操作，不换工具绕过。一个线上 Oxford 样本已完成自动保存与续跑核验，其他网站和系统界面仍需分别验证。

Windows 的 Token 从[Playwright 官方扩展](https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm)取得，通过运行 Agent 的进程环境 `PLAYWRIGHT_MCP_EXTENSION_TOKEN` 提供。缺少时 Agent 先询问并等待，程序尚不启动连接；已提供或已有可用会话则不重复索要。Token 不回显、不写入项目或发布包；它用于连接认证，网站登录与验证码仍需用户处理。

**Playwright 出现 PDF 查看器后，目前不能保证稳定自动下载。** 自动保存和目录恢复均无文件时，由用户选择仅整理题录，或保留各篇标签页，最后集中逐篇手动点击下载。保留页不得被下一篇覆盖，清单分别记录实际已打开和未打开的条目；保存后仍需逐篇核验归档。该手动队列是新增的 Skill 编排规则，尚未完成真实 Harness 验收，不承诺一键下载所有标签。

## 下载与升级

从本页 Assets 选择对应系统的 ZIP，解压后得到完整的 `cnki-download` 文件夹。两个包均包含中英文 README、Skill 指令及 `INSTALL.md`，不捆绑 Python、Node.js 或 Chrome，也不包含连接令牌、浏览器登录信息及测试论文。

| 附件 | 用途 |
|---|---|
| `academic-automation-v2.0.0-beta.4-windows.zip` | Windows 预览包，提供 `academic.cmd` |
| `academic-automation-v2.0.0-beta.4-macos.zip` | macOS 包，提供 `academic.command` 及兼容入口 |
| `SHA256SUMS` | 两个 ZIP 的 SHA-256 校验值 |

从 Beta 3 或此前测试构建升级时，整体替换 Skill 代码，保留文献目录及任务检查点。重新加载 Skill，或开启新的 Agent 会话，使新的平台规则生效；运行 `doctor` 确认版本为 `2.0.0-beta.4`。已有人工暂停按真实用户回复恢复，不删除暂停记录。

macOS 在 Skill 目录检查并连接浏览器。

```bash
./academic.command --backend apple-events --json doctor
./academic.command --backend apple-events browser connect
./academic.command --backend apple-events --json doctor --browser
```

Windows 在 Skill 目录安装锁定依赖；先提供 Token，再执行连接命令。

```powershell
npm.cmd ci --ignore-scripts
.\academic.cmd --json doctor
.\academic.cmd browser connect
.\academic.cmd --json doctor --browser
```

可选 PDF 核验依赖在 Skill 目录安装：macOS 使用 `python3 -m pip install -r requirements-pdf.txt`，Windows 使用 `py -3 -m pip install -r requirements-pdf.txt`。安装后可核验已有文件，无需重下。Chrome 使用自定义下载目录时，在命令前加 `--downloads-dir "实际目录"`。

详细步骤见 [macOS 安装](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.4/references/install-macos.md)、[Windows 安装](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.4/references/install-windows.md)和[统一命令行](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.4/references/cli.md)。

## 验证结果与待测范围

发布前离线回归共 **145 项，144 项通过，1 项隔离 Chrome 测试按配置跳过**；禁用可选第三方 Python 包后，同一套检查也通过。两个 ZIP 已核对校验和与排除项，在中文和空格路径解压后验证入口；Windows 包的共享 Python 入口在 macOS 检查，不能替代 Windows 原生入口验收。

| 真实样本 | 已有证据与限制 |
|---|---|
| PubMed PMID 37935836、28527048 | PMC 正文分别为 12、13 页，文件归档及首页题名、第一作者核验通过 |
| Oxford PMID 31647093 | 用户完成验证后，macOS Apple Events 线上自动保存成功，10 页正文身份通过，续跑未重复下载；不作为 Windows 或 Playwright 查看器成功的证据 |
| 知网中文项目式学习样本 | 修复复测取得 3 页正文并核对身份；扩展下载事件仍缺失，文件通过下载目录恢复归档 |
| DRPress 与 Frontiers | 修复复测取得可解析的 7 页和 14 页 PDF；DRPress 由 CLI 自动核对身份，Frontiers 快捷路径缺少比对元数据，另用已确认题录完成验收补核 |

这些结果来自不同阶段的本机 macOS / Codex 测试。Windows 实机、其他模型与 Harness 的行为仍待复测，中文系统保存窗口和批量保留标签页也需单独验收。历史 macOS 扩展试验保留作诊断依据，Beta 4 的 macOS 使用指引已限定为 Apple Events。

反馈请附系统与模型/Harness 版本，记录 `doctor` 的版本和代码指纹；逐篇说明是自动归档、人工保存还是待处理，并核对续跑是否产生重复文件。共享诊断前去除账号、令牌及机构跳转参数。详细证据见[验证记录](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.4/VERIFICATION.md)。Beta 3 的标签和附件保留。
