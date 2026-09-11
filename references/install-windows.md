# Windows 安装（预览版）

适用于 Windows 10/11 上能执行本地命令的 Coding Agents。真实 Windows 扩展、网站及各 Agent 验收尚待测试者完成；不要把安装成功等同于功能验收通过。

1. 下载 Release 中的 `academic-automation-v<版本号>-windows.zip`，解压得到 `cnki-download`。将完整目录放进所用 Agent 的 Skill 目录，或让 Agent 读取其 `SKILL.md`。
2. 安装 Python（代码最低 3.9，新安装建议 3.11+）、Node.js 22+ 和 Google Chrome。Chrome 使用自己的日常账户及机构权限。
3. 在 Chrome 安装[微软 Playwright 官方扩展](https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm)。需要能访问 Chrome Web Store；机构禁止扩展时不能宣称该后端可用。
4. 在解压目录打开 PowerShell，安装锁定的依赖（不需要 Git Bash、WSL 或全局 npm 安装）：

```powershell
npm.cmd ci --ignore-scripts
.\academic.cmd --json doctor
.\academic.cmd browser connect
.\academic.cmd --json doctor --browser
```

连接时在 Chrome 完成扩展授权并选择要操作的标签。执行命令的 Agent、Chrome 和文件必须在同一台电脑。扩展或浏览器没有连接时，CLI 会提示处理，不会改用新的登录配置。

若 Chrome 下载位置不是用户 Downloads，请在命令最前面加入 `--downloads-dir "D:\文献下载"`。具体检索和下载命令见[统一命令行](cli.md)，验收步骤见[平台验收](acceptance.md)。

操作结束运行 `.\academic.cmd browser disconnect`。升级时保留文献目录及其进度文件，替换 Skill 代码后重新执行 `npm.cmd ci --ignore-scripts`。不要将 `node_modules`、Chrome 配置、连接令牌或文献文件上传到仓库。
