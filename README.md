# Academic Automation Skill

> 一份可以自动化学术文献搜索和下载流程的 AI Skill。  
> An AI skill for automating academic literature search and download workflows.

**Academic Automation Skill** 是一个个人开发的 AI Skill，目标是让 AI Agent 能够通过浏览器完成重复、繁琐的学术文献检索工作，包括文献搜索、初步筛选、下载与整理。

目前支持 **CNKI（中国知网）**、**Google Scholar** 和 **Web of Science**。

本项目主要通过 **Vibe Coding** 的方式开发，并在实际的学术文献检索工作流中持续测试和改进。

---

**Academic Automation Skill** is a personal AI Skill designed to help AI agents automate repetitive academic literature workflows through a web browser, including literature searching, preliminary filtering, downloading, and organization.

It currently supports **CNKI**, **Google Scholar**, and **Web of Science**.

This project is developed primarily through **Vibe Coding** and is continuously tested and improved through real-world academic literature workflows.

---

## Features / 功能

### 自动化文献检索 / Automated Literature Search

根据用户提供的研究主题、关键词或其他检索条件，通过支持的学术数据库自动执行文献搜索。

Search supported academic databases automatically based on research topics, keywords, and other criteria provided by the user.

### 文献筛选 / Literature Filtering

根据标题、关键词、摘要及其他可获取的文献信息，对搜索结果进行初步筛选，帮助减少重复的人工浏览工作。

Perform preliminary filtering based on titles, keywords, abstracts, and other available metadata to reduce repetitive manual review.

### 文献下载 / Literature Download

在**用户自身拥有合法访问权限**的情况下，自动执行部分文献下载流程。

Academic Automation Skill does **not** provide database accounts, subscriptions, institutional access, or paid content.

All access is performed through the **user's own browser, account, subscription, and/or institutional access privileges**.

### 文献整理 / Literature Organization

对已经获取的文献及相关信息进行整理，减少下载后手工处理文献的工作量。

Organize downloaded literature and related information to reduce repetitive post-download processing.

---

# Supported Platforms / 支持的平台

| Platform / 平台 | Status / 状态 |
| --- | --- |
| CNKI / 中国知网 | Supported / 已支持 |
| Google Scholar | Supported / 已支持 |
| Web of Science | Supported / 已支持 |

不同平台可能会修改网页结构、登录方式或访问规则，因此相关自动化功能可能随平台更新而暂时失效。

Academic platforms may change their page structures, authentication mechanisms, or access policies. Some automation features may therefore temporarily stop working after platform updates.

---

# Requirements / 运行要求

## Operating System / 操作系统

由于目前依赖 Apple Event Kit 实现浏览器自动化相关功能，Academic Automation Skill 目前仅支持 macOS。

系统要求：

macOS 14 or later

Windows 版本正在与其他参与者共同开发和测试。由于 Windows 无法使用 Apple Event Kit，相关功能需要采用不同的自动化实现，因此目前尚不可用。

Linux 目前暂不支持。

Academic Automation Skill currently supports macOS only, as its browser automation functionality relies on Apple Event Kit.

System requirement:

macOS 14 or later

Windows support is currently being developed and tested with other contributors. Since Apple Event Kit is unavailable on Windows, these features require a different automation implementation and are not yet available.

Linux is currently unsupported.
## Browser / 浏览器

目前需要配合：

**Google Chrome**

使用学术数据库时，登录、机构认证和访问权限均来自用户自己的 Chrome 浏览器环境。

Authentication, institutional access, and database permissions are provided entirely by the user's own Chrome browser environment.

---

# Installation / 安装

本项目以 **AI Skill** 的形式使用。

请将 Academic Automation Skill 按照你所使用的 AI Agent / Coding Agent 的 Skill 安装方式安装到对应环境中。

The project is distributed as an **AI Skill**. Install it according to the Skill installation method supported by your AI Agent or Coding Agent.

Example (Codex / local skills folder):

```bash
cp -R . ~/.agents/skills/cnki-download
```

Agent instructions live in `SKILL.md`. Chrome needs **Allow JavaScript from Apple Events**.


目前已经在以下环境中进行过测试：

- OpenCode
- Qoder
- Cursor
- OpenAI Codex

Tested with:

- OpenCode
- Qoder
- Cursor
- OpenAI Codex

不同 Agent 对 Skill、浏览器控制和工具调用的实现存在差异，因此不能保证所有功能在不同 Agent 上具有完全相同的行为。

Skill handling, browser automation, and tool invocation may differ between agents, so identical behavior across all environments is not guaranteed.

---

# How It Works / 工作方式

Academic Automation Skill 通过 AI Agent 控制用户自己的 Chrome 浏览器，根据用户提供的研究主题、关键词或检索条件访问受支持的学术数据库，并完成检索、筛选、下载和整理等操作。

Academic Automation Skill **不会向用户提供任何数据库访问权限**。

如果某篇文献需要订阅、购买或机构授权才能访问，用户仍然必须拥有相应的合法访问权限。

Academic Automation Skill works through an AI agent controlling the user's own Chrome browser. Based on the research topic, keywords, or search criteria provided by the user, it interacts with supported academic databases to perform searching, filtering, downloading, and organization.

Academic Automation Skill **does not provide access privileges to any academic database**.

If an article requires a subscription, purchase, or institutional authorization, the user must already have the appropriate access rights.

---

# Accounts & Access / 账户与访问权限

本项目：

- 不提供 CNKI、Google Scholar 或 Web of Science 账户；
- 不包含开发者的数据库账户；
- 不向其他用户共享开发者的登录状态；
- 不向用户提供机构订阅权限；
- 不提供免费获取付费论文的功能。

用户通过本 Skill 访问学术数据库时，应使用：

**自己的浏览器 + 自己的账户 + 自己拥有的访问权限。**

---

This project:

- does not provide CNKI, Google Scholar, or Web of Science accounts;
- does not contain the developer's database credentials;
- does not share the developer's authenticated sessions;
- does not provide institutional subscriptions;
- does not provide a method to obtain paid literature for free.

When accessing academic databases through this Skill, users must use:

**their own browser + their own account + their own authorized access privileges.**

---

# CAPTCHA / 验证码

Academic Automation Skill **不会自动绕过 CAPTCHA 或类似的人机验证机制**。

当网站要求完成 CAPTCHA、人机验证或其他需要用户交互的验证步骤时，自动化流程需要暂停，并由用户本人完成验证后继续。

Academic Automation Skill **does not automatically bypass CAPTCHAs or similar human-verification mechanisms**.

If a website requires a CAPTCHA or another interactive verification step, automation should pause and allow the user to complete it manually before continuing.

---

# Third-Party Services / 第三方平台声明

Academic Automation Skill 是一个独立的个人项目。

本项目与 **CNKI（中国知网）**、**Google Scholar**、**Web of Science** 及其运营方不存在官方隶属、合作、赞助或认可关系。

相关平台名称及商标归其各自权利人所有。

用户应自行确认其使用 Academic Automation Skill 的方式符合相应数据库、机构订阅和网络环境所适用的使用规则。

Academic Automation Skill does not circumvent authentication, paywalls, CAPTCHAs, or other access-control mechanisms.

---

Academic Automation Skill is an independent personal project.

This project is not officially affiliated with, sponsored by, endorsed by, or associated with **CNKI**, **Google Scholar**, **Web of Science**, or their respective operators.

All product names and trademarks belong to their respective owners.

Users are responsible for ensuring that their use of Academic Automation Skill complies with the applicable terms and policies of academic databases, institutional subscriptions, and network environments.

Academic Automation Skill does not circumvent authentication, paywalls, CAPTCHAs, or other access-control mechanisms.

---

# Responsible Use / 注意事项

Academic Automation Skill 的目标是 **减少学术研究过程中重复、机械的浏览器操作，** 它的设计目的并不是提供数据库本身没有授予用户的访问权限。

请合理控制自动化任务的规模和频率，并尊重学术数据库及所在机构的相关规则。

---

The goal of Academic Automation Skill is to:**reduce repetitive and mechanical browser operations in academic research workflows.** It is not designed to grant users access privileges that have not already been provided by the relevant database or institution.

Please use automation at a reasonable scale and frequency and respect the applicable rules of academic databases and institutions.

---

# Development / 开发

这是一个以 **Vibe Coding** 为主要开发方式的个人项目。

项目的需求、功能方向、测试和最终发布决策由项目维护者负责，同时大量使用生成式 AI 辅助代码编写、调试、重构、文档编写和设计讨论。

主要使用的 AI 开发工具包括：

- **Cursor**
- **ChatGPT by OpenAI**

我认为 AI 辅助开发本身是这个项目开发过程的一部分，因此选择在 README 中明确说明，而不是隐藏这一点。

---

This is a personal project developed primarily through **Vibe Coding**.

Project requirements, feature direction, testing, and final release decisions are handled by the project maintainer, with extensive assistance from generative AI for coding, debugging, refactoring, documentation, and design discussions.

Major AI tools used during development include:

- **Cursor**
- **ChatGPT by OpenAI**

AI-assisted development is an intentional part of this project's development process and is therefore disclosed here explicitly.

---

# Current Status / 当前状态

Academic Automation Skill 目前仍处于持续开发阶段。

当前重点包括：

- 提高不同学术数据库检索流程的稳定性；
- 改善文献筛选和整理流程；
- 适配网站页面结构变化；
- 测试不同 AI Agent 的兼容性；
- 与其他测试参与者共同测试和开发 Windows 支持。

Bug reports、测试反馈以及兼容性反馈均欢迎提交。

---

Academic Automation Skill is under active development.

Current priorities include:

- improving search reliability across academic databases;
- improving literature filtering and organization;
- adapting to changes in database page structures;
- testing compatibility with different AI agents;
- developing and testing Windows support with other contributors.

Bug reports, testing feedback, and compatibility reports are welcome.

---

# Disclaimer / 免责声明

本项目仅提供浏览器自动化及学术工作流辅助功能。

Academic Automation Skill 不托管、不销售、不重新分发 CNKI、Google Scholar、Web of Science 或其他第三方数据库中的文献全文。

用户通过本项目进行的数据库访问由用户自己的浏览器环境、账户及访问权限完成。

项目维护者无法保证第三方网站始终允许、兼容或支持自动化访问。第三方平台的服务条款、技术措施及访问政策可能随时发生变化。

使用者应自行判断其具体使用方式是否符合适用的平台规则、机构许可协议及相关法律法规。

---

This project provides browser automation and academic-workflow assistance only.

Academic Automation Skill does not host, sell, or redistribute full-text literature from CNKI, Google Scholar, Web of Science, or other third-party databases.

Database access performed through this project relies on the user's own browser environment, account, and access privileges.

The project maintainer cannot guarantee that third-party websites will always permit, support, or remain technically compatible with automated access. Terms of service, technical measures, and access policies may change over time.

Users are responsible for determining whether their specific use complies with applicable platform rules, institutional license agreements, and laws and regulations.

---

*Academic Automation Skill is a personal project and is still evolving. If something breaks after an academic database updates its website, feel free to open an issue.*
