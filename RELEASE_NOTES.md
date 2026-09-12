# v2.0.0-beta.2：人工验证等待与下载修复

本版针对外部模型与 Harness 测试中“尚未完成验证便结束下载、转为仅记录题录”的问题，将人工交接状态与下载检查点结合：遇到验证码、登录或保存窗口时，Agent 必须提问并等待用户回复；程序保存暂停状态，阻止继续打开其他文章。用户处理后恢复原任务，先检查文件是否已经落盘，避免重复下载。

Beta 2 继续在同一个 Pre-Release 中提供 Windows 与 macOS 两个独立下载包。macOS 默认 Apple Events 路径已有真实网站实测基础，本轮通过离线回归和隔离 Chrome 测试；Windows 官方扩展仍待测试者实机验收。

## 本版修复

| 问题 | Beta 2 的处理 |
|---|---|
| 验证未完成，模型自行决定不下载 | `needs_user` 持久保存，返回 `wait_for_user: true`；更换会话名或加 `--retry` 不能解除暂停。收到实际用户回复后，通过 `browser resolve` 记录决定并恢复原任务 |
| 将待人工或下载失败写成“无机构订阅” | 删除默认推断。待人工与失败分开；只有用户明确要求跳过，才记录 `skipped_by_user`，不能据此认定无权限 |
| 用户已经保存文件，续跑仍重复请求 | 优先核验检查点对应的已存文件；需要网页操作时才继续原任务，再遇到验证则重新暂停 |
| 出版社附录被当作正文 | 优先正文元数据链接和明确的正文 PDF，排除常见附录候选，并保留实际下载来源。仍需核对题名与作者，页数不能独自证明正文身份 |
| 安全验证页、失效链接处理不足 | 补充 Cloudflare / AWS WAF 可见验证页识别；知网详情失效时返回来源 URL 和已有进度，保留已完成记录 |
| DOI 及文件名影响恢复 | 清理已识别的 DOI 追踪参数，保留 DOI 自身字符；补充作者后无空格的 `(1)` 重复文件名识别，多候选时仍不猜测 |
| 难以确认测试者安装的代码 | `doctor` 增加 `code_fingerprint`，便于同时记录版本、模型和 Harness 信息 |

旧 macOS `oa_dl.sh` 的待人工退出码由 3 统一为 **2**；新增 **6** 表示用户明确跳过。自行编写调度器的用户需要更新退出码判断，完整约定见[统一命令行说明](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.2/references/cli.md)。

程序只能约束本项目入口，不能鉴别模型编造的用户回复，也不能禁止拥有本地命令权限的 Agent 绕过入口。Harness 应在收到 `wait_for_user: true` 后暂停浏览器调度，仅在实际用户消息到达后允许调用 `browser resolve`。本版没有实现验证码绕过，也不承诺无人值守下载。

## 下载与升级

在本页 Assets 中选择对应系统的 ZIP。解压后得到完整的 `cnki-download` 文件夹，将其放入 Agent 的 Skill 目录，或让 Agent 读取其中的 `SKILL.md`。安装说明位于包内 `INSTALL.md`。

| 附件 | 用途 |
|---|---|
| `academic-automation-v2.0.0-beta.2-windows.zip` | Windows 10/11 测试包，提供 `academic.cmd` |
| `academic-automation-v2.0.0-beta.2-macos.zip` | macOS 测试包，提供 `academic.command` 及旧脚本兼容入口 |
| `SHA256SUMS` | 两个 ZIP 的 SHA-256 校验值 |

两个包共享核心源码，不捆绑 Python、Node.js 或 Chrome。Python 最低为 3.9，新安装建议使用 3.11 或更高版本；扩展后端另需 Node.js 22 或更高版本，通过包内锁定文件安装 Playwright CLI 0.1.19。

从 Beta 1 升级时，请整体替换 Skill 代码，保留个人文献目录和任务检查点；使用扩展后端时，在新目录重新安装锁定依赖。随后重新加载 Skill 或开启新的 Agent 会话，运行 `doctor` 确认版本为 `2.0.0-beta.2`。保留暂停记录，不要通过删除状态文件解除等待。

## Windows 与 macOS 的扩展要求

| 系统与连接方式 | 是否需要 Chrome 扩展 | 配置要求 | 验证状态 |
|---|---|---|---|
| Windows 默认方式 | **需要**微软 Playwright 官方扩展 | 安装 Node.js 与锁定的 npm 依赖，在 Chrome 中完成扩展授权并选择标签 | 待 Windows 测试者实机验收 |
| macOS 默认 Apple Events | **不需要扩展** | 启用 Chrome 的 Allow JavaScript from Apple Events，首次连接时授权系统自动化权限；无需 Node.js 或 npm 依赖 | Beta 1 已通过真实网站检索与下载；本轮通过行为回归 |
| macOS 可选扩展方式 | **需要**同一个官方扩展 | 安装 Node.js 与锁定的 npm 依赖，每次命令加 `--backend extension`；无需启用 Apple Events JavaScript | 官方扩展连接尚未实测 |

扩展须安装自[微软 Playwright Extension 的 Chrome Web Store 页面](https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm)，上游项目见 [Playwright CLI](https://github.com/microsoft/playwright-cli)。两种方式均沿用用户自己的已登录 Chrome，网站权限取决于账户和机构授权。

Windows 在解压后的 `cnki-download` 目录打开 PowerShell，执行：

```powershell
npm.cmd ci --ignore-scripts
.\academic.cmd --json doctor
.\academic.cmd browser connect
.\academic.cmd --json doctor --browser
```

macOS 默认方式在同一目录执行：

```bash
./academic.command --json doctor
./academic.command browser connect
./academic.command --json doctor --browser
```

macOS 如选择扩展方式，先安装上述官方扩展，再执行：

```bash
npm ci --ignore-scripts
./academic.command --backend extension browser connect
./academic.command --backend extension --json doctor --browser
```

`doctor` 检查运行环境，`doctor --browser` 再检查已连接标签。Chrome 使用自定义下载目录时，在命令最前面加入 `--downloads-dir "实际目录"`；启用“下载前询问保存位置”时，需人工处理保存窗口。结束后运行 `browser disconnect`，扩展方式保留 `--backend extension`，日常 Chrome 会继续保留。

## 验证与待测范围

本轮新增 15 项行为回归，离线套件共 52 项：**51 项通过，1 项隔离 Chrome 测试默认跳过**；原有回归全部通过。单独启用的隔离 Chrome 测试也已通过，包含模拟中文下载，以及独立 HTTP 请求无法取得 PDF 后，从真实 Chrome 的同源链接下载并保留 Referer。模拟站点结果不能代替真实出版社验收。

两个安装包已在 macOS 下解压核验，版本与默认配置正确，题录生成和校验和检查通过。macOS 包的启动入口已运行；Windows 包的 Python 入口已检查，原生 Windows 启动入口仍待实机验证。

Beta 1 已完成 macOS 默认方式下的知网中文与外文流程，并验证了 Scholar 分页、WoS 登录后分页及 DRPress 公开 PDF 下载。Beta 2 没有重新运行 ZCode/GLM-5.3，也没有重新验收 Wiley、Elsevier 或真实 AWS WAF 场景。完整记录见 [VERIFICATION.md](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.2/VERIFICATION.md)。

本版面向能执行本地命令的 Coding Agents，Agent 与 Chrome 需位于同一台电脑。Windows 实机与 macOS 可选扩展仍待验证；Cursor、OpenCode 与 Qoder 的完整流程，以及外部模型收到验证提示后是否实际等待，均需按[平台与 Harness 验收说明](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.2/references/acceptance.md)复测。真实 CAJ、跨盘文件占用和特殊保存窗口也不能由本轮 PDF 测试代替。云端桥接和独立 MCP 服务不在本版范围内。

反馈时请附系统和模型/Harness 版本、连接方式，以及 `doctor` 返回的版本与代码指纹；保留复现步骤和返回码，说明是否向用户提问、用户何时回复、文件是否落盘及续跑结果。分享记录前请去除账号、令牌和机构身份信息。
