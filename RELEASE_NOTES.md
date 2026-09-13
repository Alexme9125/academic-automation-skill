# v2.0.0-beta.3：知网自动下载与 Windows 反馈修复

Windows 测试者使用 DSH 与 DeepSeek 运行 Beta 2 时，已完成部分检索和下载，但也遇到程序操作后没有文件的情况，需要手工点击才能继续。本版以这一下载过程为例，将页面按钮点击、浏览器下载事件与文件检查点结合，补充下载结果的核验与恢复，为减少人工补点提供依据。

本版所说的“下载完成”，即文件已落盘，并经过核验和归档。扩展后端会实际点击唯一可见的 PDF/CAJ 按钮，保留网站的点击事件与详情页来源信息；浏览器返回下载事件后，程序保存对应文件，核对作者和格式，再归档。没有收到事件时则检查 Chrome 的实际下载目录，仍无可核验文件便暂停，避免在结果不明时重复点击。

Beta 3 继续作为 Pre-Release 提供 Windows 与 macOS 两个下载包。本轮修复已通过离线回归和隔离 Chrome 测试，Windows 报告中的具体文章仍需测试者复测；模拟条件下自动下载成功，不能据此认定所有知网页面与机构环境均已通过验收。

## 本版改动

| 测试中暴露的问题 | Beta 3 的处理 |
|---|---|
| 自动下载无文件，需要人工补点 | 扩展方式由读取链接跳转改为实际按钮点击，并监听当前页及新窗口的下载事件；未收到事件时先查文件，无结果则转为待人工，不追加点击 |
| 连接显示成功，随后提示会话不可用 | 扩展附着后实际读取选定标签的标题和 URL，通过才保存连接状态；发现会话失效时提示重连 |
| 页面仍在跳转，读取脚本报错 | 将结果匹配与详情导航分开；只读检查在上下文切换时最多重试三次，点击和提交不会随之重放 |
| 用户确认后，页面超时清除了暂停记录 | 页面就绪超时返回 70，保留已有待人工记录；批量遇到 70 或浏览器占用 75 时停止，留在当前篇 |
| 自写脚本遗漏任务锁与人工交接 | 公开下载及知网检索函数拒绝在统一入口之外独立调用；新增 `search cnki`，支持主题检索和专业检索，逐页保存进度 |

下载检查点还保留按钮信息与下载事件结果，保存失败时记录原因，便于区分“没有找到按钮”“点击后没有事件”与“已经收到事件但保存失败”。未确认完成的临时文件不会直接归档，也不会自动触发另一次下载。

Beta 2 的人工交接规则继续保留。遇到登录、验证码或保存窗口，Agent 应向用户提问并等待实际回复；用户完成操作后先核验已有文件，再恢复原任务。待人工、失败和用户明确跳过分别记录，不能将待人工文献改写成无权限或仅题录完成。程序约束的是本项目入口，Harness 仍须保证 `browser resolve` 来自实际用户回复。

## 下载与升级

从本页 Assets 选择对应系统的 ZIP，解压后得到完整的 `cnki-download` 文件夹，将其放入所用 Agent 的 Skill 目录，或让 Agent 读取其中的 `SKILL.md`。包内 `INSTALL.md` 提供安装步骤。

| 附件 | 内容 |
|---|---|
| `academic-automation-v2.0.0-beta.3-windows.zip` | Windows 测试包，提供 `academic.cmd` |
| `academic-automation-v2.0.0-beta.3-macos.zip` | macOS 测试包，提供 `academic.command` 和旧 macOS 兼容入口 |
| `SHA256SUMS` | 两个 ZIP 的 SHA-256 校验值 |

两个包共享 Python 核心，不捆绑运行环境。核心需要 Python 3.9 或更高版本；扩展后端按本项目安装要求使用 Node.js 22+，并通过包内锁定文件安装 Playwright CLI 0.1.19。Chrome 沿用用户自己的登录状态和机构权限。

从 Beta 2 升级时，整体替换 Skill 代码，保留文献目录及任务检查点。扩展方式须在新 Skill 目录重新安装锁定依赖，然后重新加载 Skill 或开启新的 Agent 会话，运行 `doctor` 确认版本为 `2.0.0-beta.3`，同时记录 `code_fingerprint`。不要通过删除暂停记录解除等待；自行编排任务的脚本也应改用统一 CLI。

## Windows 与 macOS 的扩展要求

| 系统与连接方式 | Chrome 扩展 | 所需设置 | 验收情况 |
|---|---|---|---|
| Windows 默认方式 | **需要 Playwright 官方扩展** | 安装 Node.js 和锁定依赖，在 Chrome 完成扩展授权并选择标签 | 已有 Beta 2 的部分实机反馈；Beta 3 修复待 Windows 复测 |
| macOS 默认 Apple Events | **不需要扩展** | 启用 Allow JavaScript from Apple Events，首次连接时授予系统自动化权限；无需 Node.js 或 npm 依赖 | Beta 1 已有真实网站检索与下载记录；本轮通过离线回归，未重新验收网站 |
| macOS 可选扩展方式 | **需要同一个官方扩展** | 安装 Node.js 和锁定依赖，后续命令均加 `--backend extension`；无需启用 Apple Events JavaScript | 隔离 Chrome 测试通过，日常 Chrome 的官方扩展附着尚未实测 |

扩展安装地址为[微软 Playwright Extension](https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm)，上游工具见 [Playwright CLI](https://github.com/microsoft/playwright-cli)。本项目使用锁定版本，按下面的命令安装即可。

Windows 在解压后的 `cnki-download` 目录打开 PowerShell，安装依赖并检查连接。

```powershell
npm.cmd ci --ignore-scripts
.\academic.cmd --json doctor
.\academic.cmd browser connect
.\academic.cmd --json doctor --browser
```

macOS 默认方式使用包内启动入口。

```bash
./academic.command --json doctor
./academic.command browser connect
./academic.command --json doctor --browser
```

macOS 若选择扩展方式，先安装上述官方扩展，再运行以下命令，后续检索与下载也保留 `--backend extension`。

```bash
npm ci --ignore-scripts
./academic.command --backend extension browser connect
./academic.command --backend extension --json doctor --browser
```

`doctor` 检查本地环境，`doctor --browser` 再读取已连接标签。Chrome 使用自定义下载目录时，在命令最前面加 `--downloads-dir "实际目录"`，供文件检查与人工恢复使用。系统保存窗口或网站验证仍可能需要用户处理，结束后可运行 `browser disconnect`，日常 Chrome 会保留。

## 中文检索入口

研究方向检索现在可以直接使用统一 CLI，专业检索式通过 `--expert` 指明。Windows 使用 `academic.cmd`，macOS 使用 `academic.command`；下面以 Windows 为例。

```powershell
.\academic.cmd --json search cnki "项目式学习" results.json --pages 2
.\academic.cmd --json search cnki "SU='孟德尔随机化' AND SU='近视'" mr-myopia.json --expert
```

输出包含命中总数及本次提取的条目，保留结果行中的原文和真实详情链接，进度写在输出旁的检查点中。当前沿用网站提交检索后的默认排序，不能将结果称为被引排序；结果行也不能代替完整详情元数据，缺失字段仍需核实。下载和人工恢复的完整用法见[统一命令行说明](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.3/references/cli.md)。

## 验证结果与待测范围

本轮新增 15 项行为回归，离线套件共 **67 项，其中 66 项通过，1 项隔离 Chrome 测试默认跳过**。单独启用的隔离 Chrome 测试通过，用时约 28.8 秒；模拟详情页的可见按钮需要真实点击事件才能发起下载，程序成功取得并归档 PDF，保留详情页 Referer，重复运行没有再次下载。隐藏的误导链接没有被选中。

同一隔离测试还回归了出版社直接下载，以及独立 HTTP 无法取得 PDF 后的浏览器下载。两个发布包在 macOS 的中文和空格路径下完成解压检查，默认后端与版本正确，启动帮助和题录生成通过；Windows 原生启动入口仍需实机验证。完整记录见 [VERIFICATION.md](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.3/VERIFICATION.md)。

测试者复测应优先使用原来需要手点的文章，检查自动点击能否产生文件、没有下载事件时是否保留待人工、人工保存后是否避免重复下载，再检查长题名和中文路径。真实 CAJ 与系统保存窗口仍需覆盖，跨盘归档及文件占用也应在 Windows 上验证。各模型和 Harness 是否实际等待用户回复，需要分别记录，不能由程序测试代替。

反馈请附系统和模型/Harness 版本、连接方式，以及 `doctor` 的版本与代码指纹；逐篇记录退出码、自动或人工保存、最终路径和续跑结果，核对初始清单与最终清单是否一致。分享下载诊断前去除账号与机构跳转参数，按[Windows DSH 复测清单](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.3/references/acceptance.md#windows-dsh-反馈修复复测)提供可复现的依据。
