# 统一命令行（Windows / macOS）

所有命令均从 Skill 根目录运行。Windows 将下列 `python3` 换成 `py -3`，或使用下载包根目录的 `academic.cmd` 代替 `python3 scripts/academic.py`；macOS 可用 `./academic.command`。Python 核心无需 pip 安装。

全局选项放在子命令之前：`--json`、`--backend extension|apple-events`、`--session NAME`、`--downloads-dir PATH`。默认 macOS 使用 Apple Events，Windows 使用 extension。`CNKI_DOWNLOADS_DIR` 可持久指定 Chrome 实际下载目录；用户自定义下载目录或开启“保存前询问”时须明确该路径。

## 连接与诊断

```text
python3 scripts/academic.py --json doctor
python3 scripts/academic.py --backend extension browser connect
python3 scripts/academic.py --backend extension --json doctor --browser
python3 scripts/academic.py --backend extension browser disconnect
```

`doctor` 只检查本机运行环境，不能证明扩展、登录或机构访问可用。`doctor --browser` 才读取连接标签的标题和 URL。首次扩展连接会出现官方扩展授权和标签选择界面；使用自己的账户完成。不同 Skill 副本共享本机浏览器任务锁，不会并行抢占。断开连接保留用户的 Chrome。

同一任务后续命令使用相同 `--backend` / `--session`，也可通过 `ACADEMIC_BROWSER_BACKEND` / `ACADEMIC_BROWSER_SESSION` 设置。默认会话名 `academic`。浏览器重启或目标标签关闭后重新连接。不要导出 cookie 或复制浏览器用户配置。

## 检索、元数据与题录

```text
python3 scripts/academic.py search scholar "value-added assessment" scholar.json --pages 2
python3 scripts/academic.py search wos "value-added assessment" wos.json --pages 2 --oa
python3 scripts/academic.py search cnki-foreign "value-added assessment" cnki.json --pages 1
python3 scripts/academic.py metadata urls.txt metadata.json
python3 scripts/academic.py bibliography scholar scholar.json bibliography.md --title "文献目录"
python3 scripts/academic.py bibliography wos wos.json bibliography.md
python3 scripts/academic.py bibliography cnki metadata.json bibliography.md
```

`urls.txt` 每行一个真实详情页 URL。CNKI 外文结果先提取详情元数据再生成外文题录；中文结果行不能伪装成完整外文元数据。Scholar 支持 `--year YYYY`、1–5 页；WoS 支持 `--oa`。检索和元数据用 `--refresh` 重取，其余时候复用 `.progress.json`。CNKI 外文中断后可能需要重新经过前面页面，但保留已抽取记录。

## 中文与 DOI 下载

```text
python3 scripts/academic.py download cnki "论文完整题名" "第一作者" "文献目录"
python3 scripts/academic.py download cnki "论文完整题名" "第一作者" "文献目录" --expert "SU='学习进阶' AND SU='化学'" --pages 3
python3 scripts/academic.py batch titles.txt
python3 scripts/academic.py download doi "10.xxxx/完整DOI" "文献目录" --name "归档文件名"
```

批量清单格式仍为 `题名|第一作者|目标文件夹`。中文可用 `--affiliation`、`--index`；批量可用 `--refresh-index`。中文未给第一作者时，在打开浏览器之前停止。

单篇进度保存在目标目录的 `.academic-downloads/`。验证码、登录或 PDF 保存窗口需人工处理；处理后重跑原命令，先检查本次快照之后的文件，再决定是否继续。没有新文件会保持暂停；明确需要重新请求时才加 `--retry`。批量遇人工步骤立即退出，不等待无交互终端输入，也不继续打开下一篇。

自动归档要求唯一、稳定且格式符合的候选。用户手动另存为时，中文文件名应保留 `_第一作者.pdf` / `_第一作者.caj` 后缀；不符合时使用显式文件归档：

```text
python3 scripts/academic.py archive "文献目录" --file "下载目录/实际文件.pdf" --name "完整题名_第一作者.pdf"
```

请先核对手动选择文件的题名与作者。若该文件属于暂停中的单篇任务，给 `archive` 加上 `--checkpoint "result.checkpoint 的实际路径"`，同时完成该任务的检查点，后续重跑会直接跳过。同名文件不会被覆盖，跨盘归档受支持。候选不唯一时不自动取“最新文件”。PDF 页数仅为辅助信息；未知页数不等同于失败。

## Agent 返回值

`--json` 输出一个 JSON 对象：`ok`、`status`、`code`、`result`。诊断信息在 stderr；文件输出仍为原有 Markdown / JSON。`status` 为 `complete`、`needs_user`、`busy` 或 `failed`。

| 退出码 | 含义 |
|---|---|
| 0 | 请求的操作完成；检索范围由页数限定 |
| 1 | 无结果、匹配歧义或流程未完成 |
| 2 | 需要登录、验证码、浏览器连接或人工保存 |
| 3 | 未发现下载链接 / DOI 未注册，查看 message |
| 4 | 无唯一、稳定且有效的下载文件 |
| 5 | 收费页或当前账户无访问权限 |
| 64 | 参数错误 |
| 69 | 缺运行环境 |
| 70 | 浏览器协议、超时或网络错误；动作可能已完成，先检查 |
| 74 | 本地文件读写或数据错误 |
| 75 | 其他任务正在使用浏览器 |
| 130 | 用户中断，可按检查点恢复 |

`needs_user` 不是成功；有部分题录也不能汇报为全部完成。旧 macOS 命令保留入口，但新 Agent 应只使用统一 CLI；不依赖旧 shell 日志作为协议。
