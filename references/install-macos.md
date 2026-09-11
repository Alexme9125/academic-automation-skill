# macOS 安装

> 新版优先使用[统一命令行](cli.md)。下列 `.sh` 示例仅为 macOS 兼容入口；Windows 使用对应的统一命令。站点选择器与匹配规则两平台共用，退出状态以新版 CLI 文档为准。

下载 `academic-automation-v<版本号>-macos.zip` 并解压，将完整 `cnki-download` 文件夹放入 Agent 的技能目录。Python 核心最低 3.9；新安装建议使用 3.11+。

默认后端为 Apple Events：Google Chrome → View → Developer → Allow JavaScript from Apple Events。使用自己的已登录 Chrome，系统首次请求应用自动化权限时按实际需要授权。

```text
python3 scripts/academic.py --json doctor
python3 scripts/academic.py browser connect
python3 scripts/academic.py --json doctor --browser
```

下载包也提供 `./academic.command` 启动入口。旧 `.sh` / `.py` 入口仍可使用，主要流程已转到共享 Python 核心。

可选扩展后端需要 Node.js 22+、[Playwright 官方扩展](https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm)，并在 Skill 目录运行 `npm ci --ignore-scripts`。随后所有命令显式使用 `--backend extension`；不需要启用 Apple Events JavaScript。

连接后操作绑定标签，不跟随用户临时切换的活动标签。目标标签关闭或浏览器重启后重新运行 `browser connect`。结束用 `browser disconnect`，不会关闭日常浏览器。

详见[统一命令行](cli.md)及[平台验收](acceptance.md)。
