---
name: cnki-download
description: 在知网中文/外文库（CNKI、WWJD）、Web of Science（WoS）或谷歌学术检索文献、整理带链接的题录目录，并按题名清单或 DOI 下载可获取的 PDF/CAJ。适用于文献检索、批量下载及归档；浏览器流程沿用用户已登录的 Chrome；Windows 使用官方扩展，macOS 支持 Apple Events。
metadata:
  version: "2.0.0-beta.1"
---

# 学术文献检索、下载与归档

## 按任务读取

先确定网站、语言与交付阶段，优先使用[统一命令行](references/cli.md)，只读取当前模式对应的参考文档。正常运行直接执行脚本，不预读全部源码、README、排错文档或其它模式。

| 用户任务 | 此时读取 | 执行入口 |
|---|---|---|
| 知网中文期刊、博硕、会议；中文题名清单 | [中文库](references/chinese-macos.md) | `download cnki`；批量 `batch` |
| 知网外文、WWJD；摘要页给 DOI 无 PDF/CAJ | [外文库](references/foreign-macos.md) | `search cnki-foreign` → `metadata` → `bibliography cnki` |
| Web of Science / WoS / Core Collection | [WoS](references/wos-macos.md) | `search wos` → `bibliography wos` |
| 谷歌学术 / Google Scholar | [Scholar](references/scholar-macos.md) | `search scholar` → `bibliography scholar` |
| 已有完整 DOI，需要实际下载外文全文 | [出版社下载](references/publisher-oa.md) | `download doi`；需要时 `archive` |
| 正常流程失败，需查页面/匹配/归档原因 | [排错](references/troubleshooting-macos.md) | 按退出码只查看相关段落 |

“只做目录”不读取出版社下载和浏览器保存细节。检索阶段不提前加载下载排错。脚本参数、特定站点选择器和经验例外放在上述参考文档；已知入口足够时不要反复读取源码。

## 对话流程

主路径：方向 → 必要时确认网站/语言 → 检索 → 必要时确认交付方式 → 执行 → 核验汇报。用户已说明或已授权的内容不重复询问。

- 现成题名清单且要求逐篇下全文：中文走中文库，英文走外文/出版社；不再问网站，缺作者或归档路径先补齐。中文下载必须提供第一作者，脚本会在打开浏览器前校验。
- 只有研究方向：网站或语言未明确时一次问清并等回答，再打开检索页。网站可选知网中文/外文、WoS、Scholar 或多个；语言可选中文、英文、中英。已经说“用 WoS”“用谷歌学术”“从知网下中文”等时直接按指定模式执行。
- 多网站/中英任务分开检索，同一浏览器串行进行。不要因为多个来源就并行抢占活动标签。
- 检索后简述大致命中数、本页提取数和主题相关性。若交付方式尚未指定，再问“能下则下”或“只做目录”；已要求下载或只要目录则直接执行。
- “能下则下”：下载当前可获取全文；无法获取的保留题录并记录实际原因。“只做目录”：只整理有发布页链接的 Markdown，不启动全文下载。

## 共用前提与约束

1. 新用户先读[平台安装](references/install-windows.md)（Windows）或[macOS 安装](references/install-macos.md)。正常任务只读[统一命令行](references/cli.md)中对应命令。默认沿用已登录 Chrome，不导出 cookie；Windows 扩展后端为预览，实机验收状态见 `VERIFICATION.md`。
2. 使用 `scripts/academic.py` 统一入口；机器调用将 `--json` 放在子命令之前。Windows 使用 `py -3`，macOS 使用 `python3`。浏览器连接后绑定选定标签，同一用户的浏览器任务串行执行。出现 `needs_user` 时停止调度，待用户处理后重跑；原始 shell 入口仅用于兼容 macOS。
3. CNKI 登录/机构权限在中文或外文模式检查；WoS 机构访问在 basic-search 检查。不要要求 Scholar 或纯离线整理任务先登录知网。机构访问与 WoS 顶栏个人 Sign In 不同。
4. 外文库/WoS 没有知网式 PDF/CAJ 按钮，禁止对这些详情页运行 `cnki_click.js`。外文全文走完整 DOI → 出版社，或真实可用的 PDF 链接。
5. 中文下载保留详情页 referrer，通过 `location.href` 跳转。不要直接 open/curl 知网下载地址。语言库状态会跨检索保留，中文检索前点回中文。
6. 验证码、人机验证、登录墙须暂停交给用户，不自动绕过。收费页记录权限原因；网络错误、链接缺失与非 OA 不混为“机构订阅”。验证码完成后先查自动续下的文件，再考虑重试。
7. 开始下载/整理前查看工作区已有分类与相关目录，复用用户归档结构，避免覆盖与重复下载。目标未指定时补齐路径。跨设备移动使用支持复制再删除的归档流程。
8. 页面等待按目标页面和内容稳定性判断，并保留超时；访问节奏与页面就绪独立。不要为提速取消作者匹配、文件稳定性验证、PDF 类型检查或验证码暂停。

## 目录与交付要求

每条文献都要有可点击的发布页链接：题名写成 `[题名](url)`，另保留 `- 链接：` 或 `- 全文：` 行。URL 优先使用出版社落地页/完整 DOI，其次知网摘要页、Scholar 题名 href、WoS full-record，最后才用侧栏 PDF 并注明来源。不能输出无 URL 的正式目录条目；未抽出链接的条目单独记为待补，不能静默当作已完成。

使用各模式的题录脚本，保持来源、题名、作者、年、DOI 等真实提取值；缺失字段不猜测。外文 DOI 可能被截断，下载前按外文参考文档补齐。只有中文搜索结果行时不要误套外文完整元数据格式。

搜索/提取进度保存在输出旁的 `.progress.json`。同参数重跑会复用已完成页/URL；要重新获取最新结果时用 `--refresh`。部分完成的结果不能汇报成全部完成。批量下载的身份与文件核验机制见中文参考文档。

全文落盘后核对实际文件类型、题名作者和归档路径；`pdf_pages.py` 给出页数辅助信息，null 不单独证明下载失败。统计排除 `._*`，CAJ 格式单独注明。

汇报目录与归档路径、已有资源、本次新增全文数、仅题录数，以及失败/待人工清单。将检索命中总数、本次抽取数与最终交付数区分开。
