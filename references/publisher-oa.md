# 出版社 OA 下载路由（macOS）

知网外文库只给题录 + DOI。先用 `cnki_full_doi.js` / `cnki_meta.js` 拿到**完整 DOI**（头部显示的可能被截断），再跑：

```bash
scripts/oa_dl.sh <DOI> <目标文件夹> [归档文件名]
```

脚本会请求 `https://doi.org/{DOI}`，按最终域名分流：**能 curl 就 curl**，被反爬再落到 Chrome。

## 各站

| 站点 | 直接 curl | 浏览器 | PDF 规律 | 备注 |
|---|---|---|---|---|
| SAGE Open | 否（403） | 页内 `location.href` | `journals.sagepub.com/doi/pdf/{DOI}?download=true` | 必须带着详情页 referrer 跳转 |
| Nature (Sci Rep 等) | 是 | 备用 | `nature.com/articles/{id}.pdf` | curl 带 UA |
| Frontiers | 是 | 备用 | `/articles/{DOI}/pdf` 或 `/journals/education/articles/{DOI}/pdf` | 先试短路径 |
| Springer | 否（HTML） | 内嵌 PDF → Cmd+S → Save | `link.springer.com/content/pdf/{DOI}.pdf` | Computer Use 点 Save / OKButton |
| SCIRP | 是 | 先打开文章页找链接 | `content.scirp.org/pdf/{id}.pdf` | 用 `pub/scirp.js` |
| Scholink (WJER) | 视情况 | download 链接可落盘 | `/article/download/{id}/{galley}` | `/article/view/` 常返回 XML/PDF.js |
| BryanHouse (JRVE/JERP) | 常可以 | 备用 | 同上 OJS download | 先 curl download |
| Stemmpress / Aeph.press | 是 | 打开文章页 | 页内 `/uploadfile/....pdf` | `pub/uploadfile.js` |

未列入的站点：打开 doi.org 跳转后的落地页，跑 `pub/find_pdf.js`，对 `.pdf` / `/article/download/` / `/uploadfile/` 先 curl；`file` 不是 PDF 再页内跳转。

## curl 模板（脚本已内置）

```bash
curl -sL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36" \
  -o /tmp/out.pdf "URL"
file /tmp/out.pdf   # 必须是 PDF document；HTML/XML = 被反爬
```

## 浏览器保存（Springer 等）

1. `oa_dl.sh` 打开 `content/pdf/{DOI}.pdf`，Chrome 内嵌查看器（`document.contentType == application/pdf`），**不会自动下载**。
2. Computer Use：Cmd+S → 保存对话框默认文件名常是 DOI 或文章 id。
3. 点 Save（辅助功能树：「Save」，ID 常为 `OKButton`）。
4. `scripts/cnki_archive_dl.sh "/目标/文件夹" "归档名.pdf"`

SAGE / OJS download 走页内跳转时，文件会进 ~/Downloads，同样用 `cnki_archive_dl.sh`，不必 Cmd+S。

## 页面摸底脚本

| 文件 | 何时用 |
|---|---|
| `scripts/pub/find_pdf.js` | 未知站点，先列出 PDF/download 链接 |
| `scripts/pub/sage.js` | SAGE 详情页 |
| `scripts/pub/scirp.js` | SCIRP |
| `scripts/pub/nature.js` | Nature |
| `scripts/pub/springer.js` | Springer 文章页（找 content/pdf） |
| `scripts/pub/scholink.js` | Scholink / BryanHouse 等 OJS |
| `scripts/pub/uploadfile.js` | Stemmpress / Aeph.press |
| `scripts/pub/jump.js` | 由 `oa_dl.sh` 填 URL 后页内跳转 |

## 完整 DOI

- `10.53469/JRVE.2025.7` → 详情页正文才是 `10.53469/JRVE.2025.7(09).12`
- 个别 DOI 出版社未注册（如 `10.70711/WEF.V3I1.7488` → doi.org 404），只记题录
- 归档名前缀用第一作者：`{author}-et-al-{slug}.pdf`
