# PubMed 检索、题录与全文

PubMed 随 2.0.0 RC1 提供官方接口与 PMC 下载。真实平台与样本结果见 [VERIFICATION.md](../VERIFICATION.md)。先遵守 [Skill 的订阅范围确认](../SKILL.md#对话流程)，已有回答直接沿用。

## 接口模式

macOS 以下用 `python3`；Windows 替换成 `py -3`。接口检索、元数据、题录以及 PMC 官方公开 PDF 不需要浏览器或 npm。`doctor --capability pubmed-data` 单独检查该能力的运行条件，网络是否畅通由实际请求验证。

```text
python3 scripts/academic.py --json doctor --capability pubmed-data
python3 scripts/academic.py --json search pubmed "cancer[Title] OR diabetes[MeSH Terms]" results.json --access-policy free-plus-bib
python3 scripts/academic.py --json search pubmed "Mendelian randomization" free.json --access-policy free-only --pages 2 --sort pub_date
python3 scripts/academic.py --json metadata selected.json metadata.json --source pubmed
python3 scripts/academic.py bibliography pubmed metadata.json bibliography.md
```

查询保留用户的布尔表达式与字段限定，不套用其他网站的短语引号。默认 Best Match（`relevance`）、每页 20 条、先取一页。`--sort pub_date` 按发表日期；`--free-full-text` 显式加免费全文筛选，`free-only` 自动加此筛选。保存实际查询转换、总命中数和本轮数量。总命中超过 10,000 时仍可取前几页，但单次请求上限 500 页；需要更多时缩小查询，不宣称已完整导出。

`metadata` 输入可为每行一个 PMID / PubMed URL 的文本文件，或 `{"access_policy":"free-only","rows":[{"pmid":"37935836"},{"pmid":"31647093"}]}`。JSON 的 `rows` 就是明确选定清单；不会自动扩张为全部检索结果。按 PMID 去重，重排或补充清单保留已完成元数据。`--refresh` 重新读取官方记录。

EFetch 保存完整作者、原始日期字段、摘要、DOI、PMCID及关联记录；勘误 DOI 不能替换原文 DOI。ELink 只接收 `Full Text Sources` 类别，免费标记是来源证据，下载后还需文件核验。

纯 PubMed 检索与元数据使用独立任务暂停，不受旧浏览器待人工记录阻塞；不会因此清除旧任务。缺少订阅范围时只暂停当前 API 任务，按返回 id 补回选择，不能把别的任务回答作为全局默认。

## 全文与续跑

```text
python3 scripts/academic.py --json download pubmed 37935836 papers --access-policy free-only
python3 scripts/academic.py --json download pubmed https://pubmed.ncbi.nlm.nih.gov/31647093/ papers --name "家系 MR.pdf" --access-policy all
python3 scripts/academic.py --json batch selected.json --source pubmed --dest papers
```

下载顺序：PMC 现行公开数据服务 → 同篇真实出版社入口或 DOI → 必要时人工保存。仅枚举该 PMCID 的元数据，不遍历整站、不使用已退役的 OA Web Service，不需要 AWS 账户或 SDK。正文 PDF 必须来自版本元数据的 `pdf_url`；优先正式发表版本，仅有作者稿时注明。多个版本无法唯一核实时暂停，由用户选择后通过 `browser resolve --pmc-version <版本>` 记录，再重跑原命令。不能用最大版本号或补充材料替代正文。

默认文件名 `PMID-<编号>.pdf`，便于 Windows 长路径控制。`--name` 仅为文件名，不含目录，最长 180 个 UTF-8 字节。目标目录过深仍可能超过 Windows 路径限制，应缩短目录。存储源链接、大小和 SHA-256；同名加序号，不覆盖原文件。归档先复制、同步和核验，再删除源文件。

PMC 与出版社公开文件共用分块传输和诊断。PMC 最多尝试 3 次，单次传输调用有 180 秒总预算；短暂截断保存 `.part` 与 `.transfer.json`，只有强 ETag、长度及本地前缀摘要一致才发 Range 续传请求，否则保留旧片段并重新接收。批次子命令超过 600 秒则停止并保存该篇状态。退出 70 后重跑原命令，不能自行切换来源或跳到另一篇掩盖问题。

macOS 仅使用 Apple Events，显式传 `--backend apple-events`，不使用 Playwright；Windows 出版社会话须安装 [Playwright 官方扩展](install-windows.md)并先提供 Token。Windows 扩展监听真实下载事件，无事件先检查下载目录，不重复点击。macOS 先尝试页内下载；确认没有落盘后，可识别 Chrome 内置 PDF 查看器的“下载”按钮及系统保存窗口，自动选目录、保存和归档，额外权限见 [macOS 安装](install-macos.md)。Windows 查看器自动保存尚不能保证稳定，受阻时先询问“仅题录”或“保留标签页、批量手动下载”，等待实际选择，见[受阻后的选择](cli.md#自动保存受阻后的选择)。

自动保存记录点击前检查点，只对当前绑定的 PDF 操作；不点 Google Drive 或覆盖确认。保存快捷键和回车仅用于已识别的保存窗口及其“前往文件夹”子窗口。程序收到不明操作结果后不重复点击，先检查任务暂存文件和下载目录；已经落盘可直接恢复。只有明确停在点击前的检查失败，才可在用户回复后重新尝试原生操作。无法识别的窗口仍由用户处理。

遇验证、登录或程序返回 `needs_user`（包括无法自动处理的保存窗口）：保持当前篇，提问并等待实际回复。正在执行的受控保存步骤由 CLI 完成。不能转来源或转下一篇来逃离暂停，也不能直接改为仅题录。用户处理后：

```text
python3 scripts/academic.py browser status
python3 scripts/academic.py browser resolve --pending-id <当前ID> --decision retry --note "用户的实际回复"
```

再重跑原下载或 batch 命令。已有文件在任何请求之前核验，保存完文件也可直接重跑恢复；明确手动文件用 `archive papers --file <PDF路径> --checkpoint <下载检查点>`。`--retry` 本身不能解除未确认的人工暂停。用户明确跳过，或选择取消当前自动下载并改为仅题录/人工队列时，才按统一交接使用 `--decision skip`，报告分别标明其选择。

批量状态保存在 `<清单>.batch-progress.json`，核对初始 PMID、当前选定 PMID、每篇状态和统计。暂停会停止后续篇目；清单重排时优先恢复仍在等待的那篇。同一份清单的 `access_policy` 会传给子命令，不作为跨任务默认值。状态目录可能含机构跳转地址，不能放进发布包。

## 可选正文核验与汇报

```text
python3 -m pip install -r requirements-pdf.txt
```

`pypdf` 是可选的。已安装时检查 PDF 可解析性、页数、首页题名和第一作者；缺少它或文字提取失败时允许归档，但报告“正文未自动核验”。已安装却无法解析、或者文件结构不完整时不能计为成功，保留诊断并暂停；旧缓存同样重验。明确题名作者不符则暂停，请核对当前文件或提供正确正文。页数不能单独证明正文身份。

报告至少区分：选定总数、已归档、已完成正文自动核验、仅题录、排除、未知、待人工和失败。说明本轮 pypdf 的使用情况及影响；未核验时必须提醒可能未发现错篇、正文与附录混淆或解析问题。安装后重跑原命令会核验已归档文件，不再下载。批量检查点可直接交给 `bibliography pubmed` 生成含最终状态的目录。

β 字形等已识别的提取歧义会返回 `identity_review`，仍不算自动通过。实际用户确认后按[人工身份核验归档](cli.md#人工身份核验归档)处理，单列人工核验数量。下载交付推荐 `bibliography pubmed metadata.json 目录.md --progress selected.json.batch-progress.json`，避免只从元数据输出 `free` 而遗漏归档状态；跳过与失败均保留题录。`discrepancies` 非空时须说明文件缺失、变更或元数据缺口。

## 官方依据

- [NCBI E-utilities 参数](https://www.ncbi.nlm.nih.gov/books/NBK25499/)：ESearch、EFetch、ELink，限速和返回上限。
- [PMC 现行公开数据服务](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/)及[桶内格式说明](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)：HTTPS 匿名访问、版本元数据和正文文件。
- NCBI 请求串行控制到每秒不超过 3 次，短暂网络错误和限流最多 3 次尝试，退出 70 后原命令续跑；可选 `NCBI_API_KEY`、`NCBI_EMAIL` 只来自环境，不能写入任务输出或发布包。

## 仅 PMC 与整批取消

`free-only` 表示只处理有免费依据的文献，仍可进入免费出版社页面；它不等于只走 PMC。有 PMCID 也不保证公开数据服务提供正文 PDF。用户明确只要 PMC 或不愿连接浏览器时，使用以下模式，不替用户默认缩小范围：

```text
python3 scripts/academic.py --json batch selected.json --source pubmed --dest papers --route pmc-only
python3 scripts/academic.py --json batch selected.json --source pubmed --dest papers --route pmc-only --on-unavailable bibliography
```

单篇 `download pubmed` 接受相同选项。`--route pmc-only` 不进入出版社或浏览器；无公开正文 PDF 时默认记 `deferred`，继续其余篇目。用户事先选择保留题录则用 `--on-unavailable bibliography`，记 `metadata_only`。这两种结果都不能报告成收费、无权限或已下载；实际访问状态仍单独保存。格式损坏、正文身份不符、版本不明确及网络异常继续按原规则暂停，不能自动吞掉错误。

PMC 模式拥有独立检查点与数据任务暂停；其他篇目可在浏览器待人工时执行。已经暂停的同一篇不能换模式、改变参数或换清单逃离确认。`browser status` 的 `api_pending` 同时列出接口与 PMC 待办，按各自 id 处理。自动模式的浏览器暂停仍会阻塞其他浏览器任务。

用户明确要求“全部停，只保留题录”，对本任务每份清单执行取消，`--note` 必须保存真实回复：

```text
python3 scripts/academic.py --json batch selected.json --source pubmed --dest papers --cancel --note "用户的实际停止回复"
```

整批取消写入 `<清单>.batch-progress.json`，已归档文件和此前明确跳过的条目保留。取消只解除该清单内匹配的待办，不清除其他任务；普通重跑或清单重排不会自动恢复下载。多份清单需分别取消，不能把取消一个当前篇等同于取消整个任务。用户后来明确要求恢复：

```text
python3 scripts/academic.py --json batch selected.json --source pubmed --dest papers --resume-cancelled --note "用户的实际恢复回复"
```

恢复时沿用所需 `--route`、订阅选择及目录；仅撤销本次整批取消产生的跳过，之前独立跳过的篇目继续保留其决定。

最终题录输入使用完整候选元数据，`--progress` 可接仅 PMC 子集的批次检查点；程序合并两者的 PMID，不会删掉子集之外的题录。汇报区分总数、已归档、暂缓、仅题录与用户跳过；取消数量是仅题录中的子项，自动/人工核验数量是已归档中的子项，不能重复相加。

## 检索式与 Windows 引号

复杂查询优先写入 UTF-8 文件（允许 BOM），将查询作为文件内容保留：

```powershell
@'
("Mendelian randomization"[TIAB] OR "Mendelian randomisation"[TIAB]) AND (myopia[TIAB] OR glaucoma[TIAB])
'@ | Set-Content -Encoding UTF8 '.\query.txt'
py -3 scripts/academic.py --json search pubmed results.json --query-file '.\query.txt' --access-policy free-only
```

查询文本与 `--query-file` 二选一；空文件会在检索前报错。Windows PowerShell 5.1 和 `.cmd` 会经历旧版原生参数传递，不能把某种引号替换当作所有 Shell 通用规则。[Microsoft 参数说明](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_parsing?view=powershell-7.5#passing-arguments-that-contain-quote-characters)。

主题检索可先用 `[TIAB]`，检查结果后再收紧 `[Title]` 或补充 MeSH 条件；方法词可保留 `[TIAB]` 和相应发表类型。标题限定可能提高精度，也可能遗漏只在摘要描述相关疾病的研究，须向用户说明取舍。保留原查询、修订查询与实际返回数量，不能由 20 条样本推断整个检索结果都相关。
