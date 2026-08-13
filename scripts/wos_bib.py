#!/usr/bin/env python3
# 把 wos_search.sh 的 JSON 写成文献目录 Markdown。
# 每条必须含发布页超链接（题名 [题名](url) + 链接/全文行）。
# 用法: wos_bib.py in.json out.md [--title "清单标题"] [--theme "说明"]
import argparse
import json
from datetime import date
from pathlib import Path


def as_http(s: str) -> str:
    s = (s or '').strip()
    if s.startswith('http://') or s.startswith('https://'):
        return s
    return ''


def doi_link(doi: str) -> str:
    doi = (doi or '').strip()
    if not doi:
        return ''
    if doi.lower().startswith('http://') or doi.lower().startswith('https://'):
        return doi
    return 'https://doi.org/' + doi.lstrip('/')


def pub_url(obj):
    doi = (obj.get('doi') or '').strip()
    href = as_http(obj.get('href') or '') or as_http(obj.get('url') or '')
    ft = as_http(obj.get('ft_url') or '') or as_http(obj.get('ft') or '')
    pdf = as_http(obj.get('pdf') or '')
    if doi:
        return doi_link(doi), 'doi'
    if href:
        return href, 'wos'
    if ft:
        return ft, 'ft'
    if pdf:
        return pdf, 'pdf'
    return '', ''


def entry(obj: dict) -> str:
    title = (obj.get('title') or '').strip() or '(无题名)'
    authors = (obj.get('authors') or '').strip()
    source = (obj.get('source') or '').strip()
    year = (obj.get('year') or '').strip()
    doi = (obj.get('doi') or '').strip()
    ut = (obj.get('ut') or '').strip()
    href = as_http(obj.get('href') or '')
    ft_label = (obj.get('ft') or '').strip()
    ft_url = as_http(obj.get('ft_url') or '')
    if not ft_url and as_http(ft_label):
        ft_url = as_http(ft_label)
        ft_label = ''
    oa = obj.get('oa')
    link, src = pub_url(obj)
    heading = f'**[{title}]({link})**' if link else f'**{title}**'
    lines = [heading]
    if authors:
        lines.append(f'- 作者：{authors}')
    if source:
        lines.append(f'- 来源：{source}')
    if year:
        lines.append(f'- 年份：{year}')
    if ut:
        lines.append(f'- WoS 入藏号：{ut}')
    if href and href != link:
        lines.append(f'- 详情：{href}')
    if doi:
        lines.append(f'- DOI：{doi}')
    if link:
        if src == 'doi':
            lines.append(f'- 全文：{link}  （WoS 本身不提供 PDF；按出版社路由尝试 OA，失败则标机构订阅）')
        elif src == 'wos':
            lines.append(f'- 链接：{link}  （WoS full-record；检索页未抽出 DOI）')
        elif src == 'ft':
            lines.append(f'- 链接：{link}  （GetFTR/出版社落地页，不是知网式 PDF 按钮）')
        else:
            lines.append(f'- 链接：{link}  （无发布页 URL，用 PDF 兜底）')
    else:
        lines.append('- 链接：（未抽出发布页；请打开详情页 /wos/woscc/full-record/ 再跑 wos_full.js）')
    if ft_url and ft_url not in (link, href):
        note = f'（{ft_label}）' if ft_label else '（GetFTR/出版社落地页，不是知网式 PDF 按钮）'
        lines.append(f'- 全文入口：{ft_url} {note}')
    if oa is True:
        lines.append('- OA：检索页有 Open Access 标识（仍须验证 PDF，付费篇也会出现「Full Text at Publisher」）')
    elif oa is False:
        lines.append('- OA：检索页未见 Open Access 标识')
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('src')
    p.add_argument('dst')
    p.add_argument('--title', default='Web of Science 文献清单')
    p.add_argument('--theme', default='')
    args = p.parse_args()
    data = json.loads(Path(args.src).read_text(encoding='utf-8'))
    rows = data.get('rows') if isinstance(data, dict) else data
    if not isinstance(rows, list):
        print('输入必须含 rows 数组', file=__import__('sys').stderr)
        raise SystemExit(1)
    query = data.get('quoted') or data.get('query', '') if isinstance(data, dict) else ''
    stats = data.get('stats', '') if isinstance(data, dict) else ''
    chunks = [
        f'# {args.title}',
        '',
        '> 检索来源：Web of Science Core Collection（webofscience.com）。WoS 不提供站内 PDF 下载，只给出题录 + 入藏号 +（常常要进详情页才有的）DOI + 出版社/GetFTR 链接。',
        f'> 检索日期：{date.today().isoformat()}',
        f'> 检索式：{query}' if query else '> 检索式：（未记录）',
        f'> WoS 计数：{stats}' if stats else '',
        '> 说明：能下的 OA 走 `oa_dl.sh`；「Full Text at Publisher」经常是订阅页。摘要页 DOI 可能为空。',
        '> 每条均含发布页链接：题名超链接 + 「全文」或「链接」行（优先 https://doi.org/{DOI}，否则 WoS full-record / GetFTR）。',
    ]
    chunks = [c for c in chunks if c is not None]
    if args.theme:
        chunks += ['', f'主题：{args.theme}']
    chunks.append('')
    for i, obj in enumerate(rows, 1):
        if not isinstance(obj, dict):
            continue
        chunks.append(f'### {i}')
        chunks.append(entry(obj))
        chunks.append('')
    Path(args.dst).write_text('\n'.join(chunks).rstrip() + '\n', encoding='utf-8')
    print(f'wrote {len(rows)} entries -> {args.dst}')


if __name__ == '__main__':
    main()
