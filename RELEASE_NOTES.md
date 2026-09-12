# 未发布：人工交接与出版社下载修复

- 将“待人工验证/保存”与失败、用户跳过分开，新增跨命令的暂停记录及 `browser resolve`；已落盘文件优先恢复，其他文章在等待期间不能继续。
- 删除“下载失败即无机构订阅”的默认文案。正文链接优先，排除常见附录，补充安全验证页、失效详情页与 DOI 追踪参数处理。
- 旧 `oa_dl.sh` 的待人工返回码统一为 2，不再映射为 3；新增 6 表示用户明确跳过。使用旧退出码判断的调用方需更新。
- `doctor` 增加代码指纹，平台验收说明增加模型/Harness 的等待与续跑检查。验证证据见 `VERIFICATION.md`。

下文保留已发布 beta.1 的说明，本节不表示其附件已经更新。

---

# v2.0.0-beta.1 跨平台预发布

本版首次在同一个 Release 中提供 Windows 与 macOS 两个独立下载包。“预发布”即供测试者安装和验证的版本，其中 macOS 默认路径已有真实网站实测，Windows 端则保留待实机验收的状态。

本次移植以日常 Chrome 中的文献检索与下载为例，将题名和作者校验与下载检查点结合，构建了两端共用的 Python 流程；浏览器连接分别采用官方扩展与 Apple Events，为不同本地 Coding Agents 调用同一套工作流提供基础。

## 下载与安装

在本页 Assets 中选择对应系统的 ZIP，解压后得到完整的 `cnki-download` 文件夹，将其放入 Agent 的 Skill 目录，或让 Agent 读取其中的 `SKILL.md`。安装说明位于包内 `INSTALL.md`，检索和下载命令见 `references/cli.md`。

| 附件 | 用途 |
|---|---|
| `academic-automation-v2.0.0-beta.1-windows.zip` | Windows 10/11 测试包，提供 `academic.cmd` |
| `academic-automation-v2.0.0-beta.1-macos.zip` | macOS 测试包，提供 `academic.command` 及旧脚本兼容入口 |
| `SHA256SUMS` | 两个 ZIP 的 SHA-256 校验值 |

两个包使用同一版本的共享源码，不捆绑 Python、Node.js 或 Chrome。Python 最低为 3.9，新安装建议使用 3.11 或更高版本；扩展后端另需 Node.js 22 或更高版本，通过包内锁定文件安装 Playwright CLI 0.1.19。

## Windows 与 macOS 的扩展要求

| 系统与连接方式 | 是否需要 Chrome 扩展 | 配置要求 | 本版实测状态 |
|---|---|---|---|
| Windows 默认方式 | **需要**微软 Playwright 官方扩展 | 安装 Node.js 与锁定的 npm 依赖，在 Chrome 中完成扩展授权并选择标签 | 待 Windows 测试者验收 |
| macOS 默认 Apple Events | **不需要扩展** | 启用 Chrome 的 Allow JavaScript from Apple Events，首次连接时授权系统自动化权限；无需 Node.js 或 npm 依赖 | 已通过本轮真实网站检索与下载实测 |
| macOS 可选扩展方式 | **需要**同一个官方扩展 | 安装 Node.js 与锁定的 npm 依赖，每次命令加 `--backend extension`；无需启用 Apple Events JavaScript | 尚未实测官方扩展连接 |

扩展须安装自[微软 Playwright Extension 的 Chrome Web Store 页面](https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm)，上游项目见 [Playwright CLI](https://github.com/microsoft/playwright-cli)。两种方式均沿用用户自己的已登录 Chrome，网站权限仍取决于用户账户和机构授权。

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

`doctor` 检查运行环境，`doctor --browser` 再检查已连接标签。若 Chrome 使用自定义下载目录，在命令最前面加入 `--downloads-dir "实际目录"`；启用“下载前询问保存位置”的用户，则需自行处理保存窗口。结束后运行 `browser disconnect`，扩展方式保留 `--backend extension`，日常 Chrome 会继续保留。

## 本次改动与验证

统一入口提供 JSON 结果，使本地 Agent 可以区分完成、失败和待人工处理状态。同一浏览器串行执行；检索结果逐页保存，题录按 URL 去重，下载前核对题名和第一作者，归档时核验文件并保留已有同名文件。遇到登录或验证码后，用户完成处理，再运行原命令，程序会先检查是否已有下载文件。

2026 年 9 月 12 日，在 macOS 27.0、Chrome 152.0.7977.83 与 Python 3.9.6 环境下，通过 Apple Events 取得了以下结果。

| 实测项目 | 结果 |
|---|---|
| 知网中文下载 | 《中高职一体化人才培养增值评价模型研究与应用》，第一作者代奕；成功归档 3 页 PDF，中文和空格路径可用 |
| 中文重复运行 | 校验已有文件后直接返回，没有再次下载 |
| 知网外文检索与题录 | `value-added assessment` 显示 412 条命中，提取本页 20 条；读取 2 篇详情的完整 DOI 并生成带链接题录，重跑使用缓存 |
| Google Scholar | 两页共 20 条去重题录，生成带链接目录，重跑使用两页缓存 |
| 出版社公开 PDF | DOI `10.54097/JXAZNN10` 经 DRPress 文章页取得 7 页 PDF 并归档 |
| Web of Science | 先提示机构登录，用户完成认证后两页提取 50 和 25 条，共 75 条；目录生成与缓存重跑通过 |
| macOS 解压包 | 中文和空格路径下启动成功；未提供 Node.js、未安装 npm 依赖时仍完成浏览器检查及真实检索下载；旧入口与批量跳过通过，断开后保留 Chrome |
| 离线回归 | 36 项通过，原有 16 项包含在内；另 1 项隔离 Chrome 测试默认跳过，单独启用后通过 |

实测修复了 macOS 页面跳转后过早读取上一页的问题，也补充了机构登录页识别；安装包中的说明链接已改为解压后可访问的位置。完整证据与待测清单见 [VERIFICATION.md](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.1/VERIFICATION.md)。

## 适用范围与测试反馈

本版面向能够执行本地命令的 Coding Agents，执行命令的 Agent 与 Chrome 需要位于同一台电脑。Codex 在本轮 macOS 验证中实际调用了统一入口；Cursor、OpenCode 与 Qoder 的完整调用兼容性仍需逐一验收，云端桥接和独立 MCP 服务不在本版范围内。

首先，共享流程保留了原有 macOS 入口，也使两端能够使用相同的题录和续跑格式，后续修复可以在同一仓库维护。其次，Windows 官方扩展尚未经过实机验证，真实跨盘归档与文件占用行为仍需测试；macOS 可选扩展、真实 CAJ 与特殊保存窗口也不能由本轮 PDF 测试代替。本版允许人工登录和保存，不承诺无人值守下载。

测试者可按[平台验收说明](https://github.com/Alexme9125/academic-automation-skill/blob/v2.0.0-beta.1/references/acceptance.md)执行，并在 Issue 中记录系统和 Agent 版本及连接方式，附上复现命令与返回码，同时说明文件是否落盘、重跑后是否恢复。反馈请去除账号、令牌和机构身份信息，便于依据可复现的结果确定正式支持范围。
