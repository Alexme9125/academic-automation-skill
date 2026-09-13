# 统一命令行（Windows / macOS）

所有命令均从 Skill 根目录运行。Windows 将下列 `python3` 换成 `py -3`，或使用下载包根目录的 `academic.cmd` 代替 `python3 scripts/academic.py`；macOS 可用 `./academic.command`。Python 核心无需 pip 安装。

全局选项放在子命令之前：`--json`、`--backend extension|apple-events`、`--session NAME`、`--downloads-dir PATH`。Skill 在 macOS 仅使用 Apple Events，浏览器命令须显式加 `--backend apple-events`；Windows 使用 extension。本页后续通用浏览器命令在 macOS 均加此前缀，不使用扩展示例。`CNKI_DOWNLOADS_DIR` 可持久指定 Chrome 实际下载目录；用户自定义下载目录或开启“保存前询问”时须明确该路径。

PubMed、知网外文、WoS、Scholar 检索及外文下载在子命令后使用共享的 `--access-policy all|free-only|free-plus-bib`。**以下涉及该参数的示例以用户已回答相应选择为前提，不能把示例中的 all 当成默认授权。** 用户未说明时先确认是否考虑订阅，拒绝后再问放弃还是保留题录；规则见 [SKILL.md](../SKILL.md#对话流程)。

## 连接与诊断

macOS 使用：

```text
python3 scripts/academic.py --backend apple-events --json doctor
python3 scripts/academic.py --backend apple-events browser connect
python3 scripts/academic.py --backend apple-events --json doctor --browser
```

以下扩展连接命令仅用于 Windows，以已完成[Token 前置步骤](#连接前的-token)为前提。

```text
python3 scripts/academic.py --json doctor
python3 scripts/academic.py --json doctor --capability pubmed-data
python3 scripts/academic.py --backend extension browser connect
python3 scripts/academic.py --backend extension browser connect --url "https://pubmed.ncbi.nlm.nih.gov/"
python3 scripts/academic.py --backend extension --json doctor --browser
python3 scripts/academic.py --backend extension browser disconnect
```

`doctor` 只检查本机运行环境，不能证明扩展、登录或机构访问可用。扩展 `browser connect` 在附着后实际读取标签标题和 URL，检查通过才保存连接状态；`doctor --browser` 可再次验证。Token 用于自动连接，仍须确认任务普通标签可用；若扩展仍显示授权或标签选择界面，由用户处理。不同 Skill 副本共享本机浏览器任务锁，不会并行抢占。断开连接保留用户的 Chrome。

连接页和扩展状态页不算普通网页。默认验证用户已选择的标签；若需要为本任务新建标签，可明确传 `--url`，不自动挑选其他现有标签。连接检查同时验证网页脚本能读取同一地址。`doctor --browser` 只证明页面可读，其 `download_verified=false` 不代表已实测下载失败，也不表示下载已通过。扩展连接令牌通过进程环境提供，不能放入项目配置或交付记录。

`doctor --capability pubmed-data` 不因缺 Chrome、Node.js 或扩展而失败，分别列出接口运行条件、浏览器能力及可选 `pypdf`。纯 PubMed 接口、题录和 PMC 公开文件不需连接浏览器。该检查不主动测试网络。

同一任务后续命令使用相同 `--backend` / `--session`，也可通过 `ACADEMIC_BROWSER_BACKEND` / `ACADEMIC_BROWSER_SESSION` 设置。默认会话名 `academic`。浏览器重启或目标标签关闭后重新连接。不要导出 cookie 或复制浏览器用户配置。

### 连接前的 Token

Windows 的 Skill 流程按“先提供 Token，再建立扩展连接”执行；macOS 不索要 Token：

1. 选择扩展后端后，运行 `--backend extension --json doctor`，只查看 `capabilities.browser.extension_token.present`，不要打印环境变量值。
2. 若为 `false` 且没有可沿用的已连接会话，向用户说明：“请从 Chrome 的 Playwright 官方扩展图标或状态页复制 Token，并将其提供给运行 Agent 的进程环境 `PLAYWRIGHT_MCP_EXTENSION_TOKEN`；提供后再开始连接。”等待实际提供。优先使用 Harness 的私密环境变量注入方式；用户已在本任务中提供时，Agent 直接向连接进程传入，不再索要。
3. 确认当前连接进程已获得该变量，再执行 `browser connect`，必要时用 `--url` 明确新建任务标签。普通网页和脚本探测通过后才开始浏览器检索。

缺少或仅含空白的 Token 时，连接入口返回退出码 2、`kind=extension_token`、`wait_for_user=true` 和 `may_continue_browser=false`；尚未启动 Playwright，也不清除已有连接元数据。提供 Token 后重跑连接即可；若另有文献 `pending.id`，仍需按原任务实际回复恢复，不能借重新连接清除暂停。

Token 只传给运行进程，不加入 CLI 参数、项目配置、终端回显、汇报或 `browser resolve --note`。`present=true` 只表示值已提供，`authentication_verified=false` 表示环境检查没有验证认证；连接失败仍需诊断扩展、所选标签及 Token 是否有效。已连接会话可能在创建时继承了 Token，后续命令无需重复索要或重新连接。Apple Events、纯接口与离线工作不受此条件约束。

Token 用于免去官方扩展的逐次连接确认；网站登录、人机验证、Cookie 遮罩及系统保存仍按各自流程处理。[官方 Token 说明](https://github.com/microsoft/playwright/blob/main/packages/extension/README.md)。

## 检索、元数据与题录

```text
python3 scripts/academic.py search cnki "项目式学习" chinese.json --pages 2
python3 scripts/academic.py search cnki "SU='孟德尔随机化' AND SU='近视'" chinese.json --expert
python3 scripts/academic.py search scholar "value-added assessment" scholar.json --pages 2 --access-policy all
python3 scripts/academic.py search wos "value-added assessment" wos.json --pages 2 --oa --access-policy free-only
python3 scripts/academic.py search cnki-foreign "value-added assessment" cnki.json --pages 1 --access-policy free-plus-bib
python3 scripts/academic.py search pubmed "Mendelian randomization" pubmed.json --pages 1 --access-policy free-only
python3 scripts/academic.py metadata selected.json pubmed-meta.json --source pubmed
python3 scripts/academic.py bibliography pubmed pubmed-meta.json pubmed.md
python3 scripts/academic.py metadata urls.txt metadata.json
python3 scripts/academic.py bibliography scholar scholar.json bibliography.md --title "文献目录"
python3 scripts/academic.py bibliography wos wos.json bibliography.md
python3 scripts/academic.py bibliography cnki metadata.json bibliography.md
```

`urls.txt` 每行一个真实详情页 URL。CNKI 外文结果先提取详情元数据再生成外文题录；中文结果行不能伪装成完整外文元数据。Scholar 支持 `--year YYYY`、1–5 页；WoS 支持 `--oa`。检索和元数据用 `--refresh` 重取，其余时候复用 `.progress.json`。CNKI 外文中断后可能需要重新经过前面页面，但保留已抽取记录。

## 中文与 DOI 下载

自定义 Harness 或编排脚本也使用本页的统一 CLI，不直接导入 `cnki.download`、`publisher.download` 或内部检索函数；直接调用返回 `USE_UNIFIED_CLI` / 64，以免遗漏任务锁与人工交接。私有实现不是受支持的外部 API。

```text
python3 scripts/academic.py download cnki "论文完整题名" "第一作者" "文献目录"
python3 scripts/academic.py download cnki "论文完整题名" "第一作者" "文献目录" --expert "SU='学习进阶' AND SU='化学'" --pages 3
python3 scripts/academic.py batch titles.txt
python3 scripts/academic.py download doi "10.xxxx/完整DOI" "文献目录" --name "归档文件名" --access-policy all
python3 scripts/academic.py download pubmed 37935836 "文献目录" --access-policy free-only
python3 scripts/academic.py batch selected.json --source pubmed --dest "文献目录"
```

批量清单格式仍为 `题名|第一作者|目标文件夹`。中文可用 `--affiliation`、`--index`；批量可用 `--refresh-index`。中文未给第一作者时，在打开浏览器之前停止。

PubMed JSON 清单使用 `{"access_policy":"free-only","rows":[{"pmid":"37935836"}]}`，`rows` 明确指定篇目，批量必须给 `--dest`。PMID 单篇也接受 PubMed URL。详细分页、原始日期、PMC 版本及正文核验见 [PubMed](pubmed.md)。`free-only` 在 PubMed 使用官方免费全文筛选，在 WoS 使用 OA 筛选；其余来源提取后分类，免费未知记录放入 `unclassified_rows`，不能据此断言收费。

单篇进度保存在目标目录的 `.academic-downloads/`。验证码、登录或 PDF 保存窗口需人工处理；处理后重跑原命令，先检查本次快照之后的文件，再决定是否继续。没有新文件会保持暂停；明确需要重新请求时才加 `--retry`。批量遇人工步骤立即退出，不等待无交互终端输入，也不继续打开下一篇。

首次归档、人工归档和续跑均检查 PDF 结构；安装 `pypdf` 时同时检查可解析性，已取得题名作者时再核对身份。损坏文件不会缓存为完成，返回 `kind=invalid_file` 并保留原件；用户实际确认重取后，用下述交接恢复，同名原文件不会覆盖。结果的 `download_route` 区分扩展事件、下载目录恢复、直接 HTTP 和原生保存，`verification.content_verified` 单独表示正文身份核验。

## 人工交接与调度约束

`needs_user` 是暂停状态，尚未判定该文献无法获取。Agent 必须向用户提出具体问题，例如“《题名》的出版社页面正在进行人机验证，请在当前 Chrome 标签完成后回复我；若希望跳过这篇，请明确说明”，随后等待实际回复。没有提问工具的 Harness 使用普通消息并结束当前执行轮，保留任务待续；超时不是用户回复。不能仅给“建议稍后手动下载”就把任务标记完成。

程序在本机状态目录保存 `pending-user.json`。返回值附带 `wait_for_user: true`、`may_continue_browser: false`、`pending.id` 及可复用的 `resume_argv` 参数数组。此时其他检索、元数据、下载及旧导航/JS 入口会返回 2；更换会话名或加 `--retry` 不会解除暂停。离线题录整理、查看 `browser status`、环境检查与断开连接仍可执行。

用户完成当前页面操作并回复后，先检查是否已有文件：重跑原下载命令可仅核验文件并完成检查点，`archive --file ... --checkpoint ...` 也可明确归档当前篇。若仍需网页操作，记录本次实际回复再运行原命令：

```text
python3 scripts/academic.py --json browser status
python3 scripts/academic.py --json browser resolve --pending-id "返回的 pending.id" --decision retry --note "用户实际回复"
```

当 `pending.details.kind` 为 `access_policy` 时，先完成两步订阅范围确认，再在上面命令追加 `--access-policy <用户选择>`，补回原任务。为 `pmc_version` 时，请用户从返回的版本元数据中明确选择，并追加 `--pmc-version <版本>`。这些选择都不能由等待超时或模型猜测代替。

`resolve` 成功只表示已记录决定，不表示文献已下载。随后重跑 `resume_argv` 对应的原任务（批量可重跑原清单），先查文件再进行一次恢复尝试。再次遇到验证时重新暂停；获准恢复期间其他文章仍被拦住。

页面等待超时和跳转竞态属于暂时性错误，返回 70，保留已有 pending；批量在 70 或 75 时也停止，不打开下一篇。只读探测会有限重试上下文切换，点击、提交和下载不会因此自动重放。检查当前页面及下载文件后，再恢复原任务。

用户明确要求跳过当前篇，或按下节选择结束当前自动下载并改为仅题录/人工队列后，才调用 `browser resolve --pending-id "..." --decision skip --note "用户实际回复及交付选择"`。CLI 的 `skipped_by_user` 表示取消这项自动下载；最终文献报告须按实际选择标成“用户跳过”“用户选择仅题录”或“待手动下载”，不能改写成“无权限”。重跑已跳过的自动任务返回退出码 6 / `skipped`；用户后来要求重新尝试，可用原 `pending-id` 再记录 `retry` 决定。

### 自动保存受阻后的选择

Playwright 下正文已打开、自动保存及目录恢复均无文件时，先问：“本轮这类文献是仅整理题录，还是保留各篇标签页，最后由你批量手动点击下载？”这不是默认跳过授权；等待用户的实际选择。登录、验证码与 Cookie 遮罩仍先按原交接处理，不能直接判成无法下载。

- **仅整理题录**：用户明确改为仅题录后，按上节取消当前自动下载，生成含真实来源链接的目录，标记“用户选择仅题录”；不算全文已归档。
- **保留标签页、批量手动下载**：先将本轮选定篇目写入任务目录的 `待手动下载.md`，记录题名、作者、真实详情/正文链接、已有文件、下载检查点、暂停 ID、当前标签是否已保留及保存目录。收到选择后取消受阻的自动下载，理由写明“用户改为保留标签页、稍后手动下载”；保留原页。其余篇目按清单串行新建任务标签，不能在保留页上运行 `download` / `search` 去导航下一篇，也不能关闭已保留页。只把实际确认打开的标签标成“已打开”，其余保持“未打开”。

Windows 可在 Token 已提供且当前自动下载已按实际回复结束后，用统一入口为下一篇新建标签；URL 必须来自本轮已核对的清单：

```text
py -3 scripts/academic.py --backend extension --session <本轮会话> browser connect --url "<下一篇真实详情页或正文URL>"
```

每次确认旧页仍保留、绑定的是新页，再处理下一条。连接或验证再度受阻时保留现状并说明所需动作，不反复重连；不能保留旧页时暂停准备，交付清单和真实已打开数量。用户选择批量手动下载后不再运行自动下载批次，而是请用户在保留标签中集中逐篇点击下载和保存；这不是一键下载所有标签的承诺。

用户保存后按题名、作者与文件内容逐篇核验。已有下载检查点使用 `archive <目录> --file "<明确文件>" --checkpoint "<该篇检查点>"`；没有检查点的文件也须先核对篇目，再用 `archive --file`。不能按“最新文件”猜归属，也不能只凭浏览器标签打开就计为已下载。汇报单列“待手动下载”，自动批次中的 `skipped` 不代替人工队列状态。

不要编造用户回复、删除暂停文件、切换状态目录，或绕到自写 curl/浏览器脚本继续任务。该机制约束本项目入口；拥有本地命令权限的模型仍能绕开它，所以 Harness 也应在接到 `needs_user` 后中止浏览器调度，并且仅在收到用户消息后提供 `resolve` 调用。

自动归档要求唯一、稳定且格式符合的候选。用户手动另存为时，中文文件名应保留 `_第一作者.pdf` / `_第一作者.caj` 后缀；不符合时使用显式文件归档：

```text
python3 scripts/academic.py archive "文献目录" --file "下载目录/实际文件.pdf" --name "完整题名_第一作者.pdf"
```

请先核对手动选择文件的题名与作者。若该文件属于暂停中的单篇任务，给 `archive` 加上 `--checkpoint "result.checkpoint 的实际路径"`，同时完成该任务的检查点，后续重跑会直接跳过。同名文件不会被覆盖，跨盘归档受支持。候选不唯一时不自动取“最新文件”。PDF 页数仅为辅助信息；未知页数不等同于失败。

## Agent 返回值

`--json` 输出一个 JSON 对象：`ok`、`status`、`code`、`result`。诊断信息在 stderr；文件输出仍为原有 Markdown / JSON。`status` 为 `complete`、`needs_user`、`skipped`、`busy` 或 `failed`。

| 退出码 | 含义 |
|---|---|
| 0 | 请求的操作完成；检索范围由页数限定 |
| 1 | 无结果、匹配歧义或流程未完成 |
| 2 | 需要范围选择、版本确认、正文身份核对、登录、验证码、浏览器连接或人工保存 |
| 3 | 未发现正文下载链接 / DOI 未注册 / 来源页失效，查看 message |
| 4 | 无唯一、稳定且有效的下载文件 |
| 5 | 收费页或当前账户无访问权限 |
| 6 | 用户已明确跳过，不能当成下载成功或无权限 |
| 64 | 参数错误 |
| 69 | 缺运行环境 |
| 70 | 浏览器协议、超时或网络错误；动作可能已完成，先检查 |
| 74 | 本地文件读写或数据错误 |
| 75 | 其他任务正在使用浏览器 |
| 130 | 用户中断，可按检查点恢复 |

`needs_user` 不是成功；有部分题录也不能汇报为全部完成。旧 macOS 命令保留入口，但新 Agent 应只使用统一 CLI；不依赖旧 shell 日志作为协议。

PubMed 下载的 `result.verification.content_verified` 表示首页题名作者检查结果；`result.path` 表示已经归档，两者必须分别统计。未安装 pypdf、解析或文字提取失败时仍可归档，会附带 `verification.warning`；最终必须向用户说明用途、安装方法和可能遗漏的问题。已知身份不符返回 2，不归入正文成功。批量的 `summary.archived`、`summary.content_verified` 和 `pdf_verification_note` 用于最终汇报。
