# 平台与 Agent 验收

记录操作系统、Chrome、Python、Node.js、Playwright CLI、扩展及 Agent 版本。输出报告只保留必要结果，不包含 cookie、令牌或机构身份数据。Windows 当前需要测试者实机验收。

## 离线检查

从源码或解压包运行（Windows 将 `python3` 换成 `py -3`）：

```text
python3 -B -X utf8 -m unittest discover -s tests -v
python3 scripts/academic.py --json doctor
```

普通测试不连接浏览器。环境中的 Node.js 用于 JavaScript 行为测试。可选隔离 Chrome 测试需要先运行 `npm ci --ignore-scripts`，再设置 `ACADEMIC_BROWSER_TESTS=1` 运行测试；只启动临时测试浏览器，不代表官方扩展已验收。

## 真实浏览器验收

1. 使用日常已登录 Chrome，运行 `browser connect`，在官方扩展界面选定标签，运行 `doctor --browser` 确认标题与 URL。
2. CNKI 中文：用自己有访问权限的一篇论文的完整题名和第一作者下载；核对题名作者、PDF/CAJ 类型、实际路径。输出目录使用含中文和空格的路径。
3. CNKI 外文：检索一页，提取两条详情元数据，核对完整 DOI 和生成的链接目录。
4. Scholar：检索两页，核对重复 URL 去重和重复运行的缓存使用。WoS：检索两页，核对虚拟列表累计数量。
5. 出版社：验证一次直接 OA PDF、一次浏览器触发下载，以及一次人工保存 PDF 后重跑原命令。
6. 手动触发中断后续跑；遇真实验证码时由用户处理，确认不会自动绕过、重复下载或跳到下一篇。无需刻意诱发平台限制。
7. 重排含重复条目的批量清单，确认已核验文件跳过；检查同名目标不会覆盖、跨盘归档和文件占用错误可恢复。
8. 同时启动两个浏览器操作，第二个应返回 75；断开后日常 Chrome 和其他标签保留。

## Agent 验收

分别让 Codex、Cursor、OpenCode、Qoder 读取同一 `SKILL.md` 并执行环境检查、一次题录生成、一次已授权的检索/下载，以及人工暂停后恢复。每个平台和 Agent 分开记录通过、失败或未测试；历史 macOS 版本的结果不能代替本版验证。

测试者提交：环境版本、命令、返回码、实际文件类型/数量、失败信息与是否能重跑恢复。只有实测通过的组合才可从“预览/待验收”改为“支持”。
