# 2.0.0-beta.1 — Cross-platform preview

同一个版本提供 Windows 和 macOS 两个平台包。共享 Python 工作流，Windows 通过 Playwright CLI 0.1.19 与官方 Chrome 扩展复用用户的登录会话；macOS 默认保留 Apple Events。

- 统一命令行与 JSON 结果，保留原有题录及批量进度格式。
- 中文与 DOI 下载检查点、人工保存后恢复、文件核验与不覆盖归档。
- 原 macOS 脚本入口兼容；Windows 不依赖 shell 脚本。
- 运行环境单独安装，扩展依赖使用 `package-lock.json` 固定。

下载附件：`academic-automation-v2.0.0-beta.1-windows.zip`、`academic-automation-v2.0.0-beta.1-macos.zip`、`SHA256SUMS`。Windows 网站/扩展及各 Agent 的真实验收待完成，具体证据以 `VERIFICATION.md` 为准。本版不承诺无人值守下载。

旧 shell 日志不再是推荐的机器接口；自动调用应改用 `scripts/academic.py --json`。旧 `oa_dl.sh` 仍接受 DOI、目录和可选文件名，人工保存返回 3；新 CLI 使用统一退出码 2 表示待人工。

维护者生成附件：`python3 scripts/build_release.py`。检查两个包、校验文件和验收记录后再决定公开发布；构建脚本不会创建 Git tag、上传附件或发布 Release。
