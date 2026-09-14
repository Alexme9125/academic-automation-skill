# Academic Automation Skill

[English](README.md) | **简体中文**

> **重要权限与安全提示：本 Skill 会让 Agent/Harness 在执行 macOS 界面自动化及 PDF 原生保存时，向你索要系统无障碍（辅助功能）权限，以及控制 Chrome / System Events 的自动化权限。无障碍权限允许应用控制系统界面，授权范围不限于单个网页。若有任何安全顾虑，请勿使用本 Skill，也不要授予相关权限。**
>
> **此提示随 Windows 和 macOS 两个包分发。Windows 当前通过 Playwright 扩展操作网页，系统保存窗口由用户处理。请审慎判断所用 Agent/Harness 请求的任何额外系统控制权限。**

**2.0.0 RC1 候选版**已纳入 Beta 4 后的 PubMed 传输与正文核验修复，新增仅 PMC 下载模式、整批取消与 Windows 查询文件入口。详细变化见[发布说明](RELEASE_NOTES.md)，实测范围见[验证记录](VERIFICATION.md)。

macOS 浏览器流程**仅使用 Apple Events**；Windows 使用 Playwright 官方扩展，新连接前需提供 Token。纯 PubMed 接口与明确选择的仅 PMC 下载不需要浏览器或扩展。Playwright 查看器自动保存受阻时仍需询问用户如何交付。[Latest Release](https://github.com/Alexme9125/academic-automation-skill/releases/latest) 提供 Windows、macOS，以及 macOS 可选的 [Legacy Version 1](LEGACY.md)。各包不捆绑运行环境，安装前请阅读 [Windows 安装](references/install-windows.md)或 [macOS 安装](references/install-macos.md)。

> 一份 AI Skill，用来自动化学术文献搜索和下载流程。

**Academic Automation Skill** 是一个个人开发的 AI Skill，旨在让 AI Agent 能够通过浏览器完成重复、繁琐的学术文献检索工作，包括文献搜索、初步筛选、下载与整理。

目前支持 **PubMed**、**CNKI（中国知网）**，以及 **Google Scholar** 和 **Web of Science**。

本项目主要通过 **“Vibe Coding”** 的方式开发，并在实际的学术文献检索工作流中持续测试和改进。

---

## 功能

### 自动化文献检索

用户给出研究主题、关键词或其他检索条件后，在所支持的学术数据库中自动执行文献搜索。

### 文献筛选

根据标题、关键词，以及摘要等可获取的文献信息，初步筛选搜索结果，帮助减少重复的人工浏览工作。

### 文献下载

在**用户自身拥有合法访问权限**的情况下，自动执行部分文献下载流程。

**Playwright 在出现 PDF 查看器时，尚不能保证稳定自动下载。** 自动保存及目录恢复均未得到文件时，Agent 会先询问“仅整理题录”或“保留各篇标签页，由用户批量手动点击下载”，收到选择后再调整交付；手动保存后仍须核验归档。

Academic Automation Skill 本身不提供数据库账户，也不提供订阅、机构访问权限或付费内容。

全部访问都使用用户自己的浏览器，用到的也是**用户本人的账户、订阅或机构访问权限**。

### 文献整理

整理已经获取的文献及相关信息，减少下载后手工处理文献的工作量。

---

## 支持的平台

| 平台 | 状态 |
| --- | --- |
| PubMed | 预览支持，官方接口与 PMC 下载 |
| 中国知网（CNKI） | 已支持 |
| Google Scholar | 已支持 |
| Web of Science | 已支持 |

不同平台可能会修改网页结构、登录方式或访问规则，所以相关自动化功能可能随平台更新而暂时失效。

---

## 运行要求

### 操作系统

Windows 10/11：通过 Playwright CLI 与官方 Chrome 扩展连接日常浏览器。测试者已回报 PubMed 检索、题录和两篇 PMC 下载；RC1 的扩展及出版社流程仍待 Windows 实机验收。

macOS：仅通过 Apple Events 控制 Chrome，原生保存使用 System Events；Skill 不使用 Playwright，也不将其作为故障回退方案。

Python 核心需要 Python 3.9 或更高版本（新安装建议使用仍受支持的版本）。扩展后端还需要 Node.js 22 或更高版本及固定的 npm 依赖。Linux 只声明离线数据处理支持。

### 浏览器

目前需要配合：

**Google Chrome**

使用学术数据库时，登录、机构认证和访问权限均来自用户自己的 Chrome 浏览器环境。

---

## 安装

本项目以 **AI Skill** 的形式使用。

请按你所使用的 AI Agent / Coding Agent 的 Skill 安装方式，将 Academic Automation Skill 安装到对应环境中。

下面以 Codex 的本地技能目录为例。

```bash
cp -R . ~/.agents/skills/cnki-download
```

Agent 操作说明见 `SKILL.md`。macOS 需勾选 **Allow JavaScript from Apple Events**，浏览器命令使用 `--backend apple-events`；Windows 扩展按平台安装说明配置，并在连接前提供 Token。

历史 macOS 版本曾在以下环境中测试；新跨平台版本的兼容性仍需重新验收：

- OpenCode
- Qoder
- Cursor
- OpenAI Codex

不同 Agent 对 Skill、浏览器控制和工具调用的实现存在差异，所以不能保证所有功能在不同 Agent 上表现完全一致。

---

## 工作方式

Academic Automation Skill 通过 AI Agent 控制用户自己的 Chrome 浏览器，根据用户提供的研究主题、关键词或检索条件访问所支持的学术数据库，并完成检索、筛选、下载和整理。

Academic Automation Skill **不会向用户提供任何数据库访问权限**。

如果某篇文献需要订阅、购买或机构授权才能访问，用户仍然必须拥有相应的合法访问权限。

---

## 账户与访问权限

本项目不提供任何数据库账户或访问权限。

- 不提供 CNKI、Google Scholar 或 Web of Science 账户；
- 不包含开发者的数据库账户；
- 不向其他用户共享开发者的登录状态；
- 不向用户提供机构订阅权限；
- 不提供免费获取付费论文的功能。

用户通过本 Skill 访问学术数据库时，应使用：

**自己的浏览器 + 自己的账户 + 自己拥有的访问权限。**

---

## 验证码

Academic Automation Skill **不会自动绕过 CAPTCHA 或类似的人机验证机制**。

网站要求完成 CAPTCHA、人机验证或其他需要用户交互的验证步骤，自动化流程需要暂停，并由用户本人完成验证后继续。

---

## 第三方平台声明

Academic Automation Skill 是一个独立的个人项目。

本项目与 **CNKI（中国知网）**、**Google Scholar**、**Web of Science** 及其运营方不存在官方隶属、合作、赞助或认可关系。

相关平台名称及商标归其各自权利人所有。

用户应自行确认其使用 Academic Automation Skill 的方式符合规则，也就是相应数据库、机构订阅和网络环境所适用的使用规则。

Academic Automation Skill 不绕过身份验证与付费墙，也不绕过验证码等访问控制机制。

---

## 注意事项

Academic Automation Skill 的目标是**减少学术研究过程中重复、机械的浏览器操作**，它的设计目的并不是提供数据库本身没有授予用户的访问权限。

请合理控制自动化任务的规模和频率，并尊重学术数据库及所在机构的相关规则。

---

## 开发

这是一个以 **Vibe Coding** 为主要开发方式的个人项目。

项目的需求、功能方向、测试和最终发布决策由项目维护者负责，同时大量使用生成式 AI 辅助代码编写与调试，也用于重构、文档编写和设计讨论。

开发中主要用到这几个 AI 工具。

- **Cursor**
- **ChatGPT by OpenAI**

我认为 AI 辅助开发本身是这个项目开发过程的一部分，所以选择在 README 中明确说明，而不是隐藏这一点。

---

## 当前状态

Academic Automation Skill 目前仍处于持续开发阶段。

当前的重点有这几项。

- 提高不同学术数据库检索流程的稳定性；
- 改善文献筛选和整理流程；
- 适配网站页面结构变化；
- 测试不同 AI Agent 的兼容性；
- 与其他测试参与者共同测试和开发 Windows 支持。

Bug reports、测试反馈以及兼容性反馈均欢迎提交。

---

## 更新日志

- **1.6.0** (2026-09-12) — 降低初始上下文占用并支持断点续跑：
  - 流程与排错参考文档按需加载；`SKILL.md` 从 13,696 缩至 3,108 字符，减少 77.3%。
  - 按页面稳定状态与文件完成状态等待；WoS 滚动时累计保留被虚拟列表回收的记录，下载等待期间持续识别收费页或验证码。
  - 检索分页与元数据采集支持续跑；批量条目按文献身份去重；专业检索索引缓存 24 小时，命中后仍实时核对详情。
  - 中文下载启动前统一校验第一作者；未知出版社使用共享单标签导航。
  - 新增 16 项回归测试与[验证记录](VERIFICATION.md)，覆盖真实 CNKI、WoS、Scholar 及 OA 下载流程。
- **1.5.1** (2026-08-26) — 中文库匹配与落盘纠错：题名检索改 `korder=TI`；精确匹配优先（多条包含匹配不再取首条）；短题名无作者退出 64；`--affiliation` 带上 `TI=`/`AU=`；点下载前后轮询详情/收费/验证页；按 mtime 归档；验证码先查落盘；同 tab 导航覆盖 WoS/Scholar/外文；状态表两种表头；无 URL 题录不写入清单。
- **1.5.0** (2026-08-26) — 中文库下载稳定性：
  - `cnki_dl.sh`：结果行作者校验（短题名 ≤6 字必须给作者）；`--expert` 专业检索（`SU='A' AND SU='B'`，绕开点不动的高级检索按钮）；`--affiliation` 机构过滤；检索 URL 自动去掉 `《》〈〉""——`；NOMATCH 自动翻最多 3 页（`--pages`）；同 tab `set URL` + 跳转前 `window.stop()`；退出码 5 识别 `bar.cnki.net/bar/fee` 收费页。
  - 新增 `scripts/cnki_batch.py`：`i/N` 进度、按序号定位的幂等状态表、验证码暂停续传、每 10 篇清理前置窗口多余标签。
  - 新增 `scripts/cnki_next.js`、`scripts/cnki_url.js`。
  - `SKILL.md`：动手前先扫工作区、专业检索用法、「已知坑」（zsh `IFS`、跨设备 `shutil.move`、JS 返回值、`bar.cnki.net` 订单页耗时）。
- **1.4.1** — 知网外文库（WWJD）、带引号短语检索、DOI 补全、出版社 OA 分流（`oa_dl.sh`）、Web of Science / 谷歌学术流程。

---

## 免责声明

本项目仅提供浏览器自动化及学术工作流辅助功能。

Academic Automation Skill 不托管、不销售、不重新分发 CNKI、Google Scholar、Web of Science 或其他第三方数据库中的文献全文。

用户通过本项目进行的数据库访问，由用户自己的浏览器环境、账户及访问权限完成。

项目维护者无法保证第三方网站始终允许、兼容或支持自动化访问。第三方平台的服务条款、技术措施及访问政策可能随时发生变化。

使用者应自行判断其具体使用方式是否符合适用的平台规则、机构许可协议及相关法律法规。

---

*Academic Automation Skill 是一个还在不断更新迭代的个人项目。学术数据库更新网页之后，如果哪个环节失效了，欢迎开一个 issue。*
