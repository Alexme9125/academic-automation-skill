# PubMed 检索、题录与全文

本页适用于未公开发布的 PubMed 测试构建。真实平台与样本结果见 [VERIFICATION.md](../VERIFICATION.md)。先遵守 [Skill 的订阅范围确认](../SKILL.md#对话流程)，已有回答直接沿用。

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

## 全文与续跑

```text
python3 scripts/academic.py --json download pubmed 37935836 papers --access-policy free-only
python3 scripts/academic.py --json download pubmed https://pubmed.ncbi.nlm.nih.gov/31647093/ papers --name "家系 MR.pdf" --access-policy all
python3 scripts/academic.py --json batch selected.json --source pubmed --dest papers
```

下载顺序：PMC 现行公开数据服务 → 同篇真实出版社入口或 DOI → 必要时人工保存。仅枚举该 PMCID 的元数据，不遍历整站、不使用已退役的 OA Web Service，不需要 AWS 账户或 SDK。正文 PDF 必须来自版本元数据的 `pdf_url`；优先正式发表版本，仅有作者稿时注明。多个版本无法唯一核实时暂停，由用户选择后通过 `browser resolve --pmc-version <版本>` 记录，再重跑原命令。不能用最大版本号或补充材料替代正文。

默认文件名 `PMID-<编号>.pdf`，便于 Windows 长路径控制。`--name` 仅为文件名，不含目录，最长 180 个 UTF-8 字节。目标目录过深仍可能超过 Windows 路径限制，应缩短目录。存储源链接、大小和 SHA-256；同名加序号，不覆盖原文件。归档先复制、同步和核验，再删除源文件。

macOS 默认 Apple Events，不装扩展；Windows 出版社会话必须安装 [Playwright 官方扩展](install-windows.md)。macOS 也可选同一扩展后端。两端扩展监听真实下载事件；无事件先检查下载目录，不重复点击。Apple Events 先尝试页内下载；确认没有落盘后，可识别 Chrome 内置 PDF 查看器的“下载”按钮及 macOS 保存窗口，自动选目录、保存和归档，额外权限见 [macOS 安装](install-macos.md)。该原生保存暂不用于扩展后端或 Windows。

自动保存记录点击前检查点，只对当前绑定的 PDF 操作；不点 Google Drive 或覆盖确认。保存快捷键和回车仅用于已识别的保存窗口及其“前往文件夹”子窗口。程序收到不明操作结果后不重复点击，先检查任务暂存文件和下载目录；已经落盘可直接恢复。只有明确停在点击前的检查失败，才可在用户回复后重新尝试原生操作。无法识别的窗口仍由用户处理。

遇验证、登录或程序返回 `needs_user`（包括无法自动处理的保存窗口）：保持当前篇，提问并等待实际回复。正在执行的受控保存步骤由 CLI 完成。不能转来源或转下一篇来逃离暂停，也不能直接改为仅题录。用户处理后：

```text
python3 scripts/academic.py browser status
python3 scripts/academic.py browser resolve --pending-id <当前ID> --decision retry --note "用户的实际回复"
```

再重跑原下载或 batch 命令。已有文件在任何请求之前核验，保存完文件也可直接重跑恢复；明确手动文件用 `archive papers --file <PDF路径> --checkpoint <下载检查点>`。`--retry` 本身不能解除未确认的人工暂停。只有用户明确跳过时使用 `--decision skip`。

批量状态保存在 `<清单>.batch-progress.json`，核对初始 PMID、当前选定 PMID、每篇状态和统计。暂停会停止后续篇目；清单重排时优先恢复仍在等待的那篇。同一份清单的 `access_policy` 会传给子命令，不作为跨任务默认值。状态目录可能含机构跳转地址，不能放进发布包。

## 可选正文核验与汇报

```text
python3 -m pip install -r requirements-pdf.txt
```

`pypdf` 是可选的。已安装时检查 PDF 可解析性、页数、首页题名和第一作者；缺少它、解析或文字提取失败时允许归档，但报告“正文未自动核验”。明确题名作者不符则暂停，请核对当前文件或提供正确正文。页数不能单独证明正文身份。

报告至少区分：选定总数、已归档、已完成正文自动核验、仅题录、排除、未知、待人工和失败。说明本轮 pypdf 的使用情况及影响；未核验时必须提醒可能未发现错篇、正文与附录混淆或解析问题。安装后重跑原命令会核验已归档文件，不再下载。批量检查点可直接交给 `bibliography pubmed` 生成含最终状态的目录。

## 官方依据

- [NCBI E-utilities 参数](https://www.ncbi.nlm.nih.gov/books/NBK25499/)：ESearch、EFetch、ELink，限速和返回上限。
- [PMC 现行公开数据服务](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/)及[桶内格式说明](https://pmc-oa-opendata.s3.amazonaws.com/README.txt)：HTTPS 匿名访问、版本元数据和正文文件。
- NCBI 请求串行控制到每秒不超过 3 次，短暂网络错误和限流最多 3 次尝试，退出 70 后原命令续跑；可选 `NCBI_API_KEY`、`NCBI_EMAIL` 只来自环境，不能写入任务输出或发布包。
