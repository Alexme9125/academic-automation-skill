#!/usr/bin/env python3
# 把 gs_search.sh 的 JSON 写成文献目录 Markdown。
# 每条必须含发布页超链接（题名 [题名](url) + 链接行；无 href 时用侧栏 PDF 兜底）。
# 用法: gs_bib.py in.json out.md [--title "清单标题"] [--theme "说明"]
import argparse, json, re, sys
from datetime import date
from pathlib import Path


def split_authors_line(line: str):
    line = (line or '').strip()
    authors, venue, year, publisher = '', '', '', ''
    parts = [p.strip() for p in re.split(r'\s+-\s+', line) if p.strip()]
    if parts:
        authors = parts[0]
    if len(parts) >= 2:
        mid = parts[1]
        ym = list(re.finditer(r'\b((?:19|20)\d{2})\b', mid))
        if ym:
            year = ym[-1].group(1)
            venue = mid[:ym[-1].start()].strip(' ,')
        else:
            venue = mid
    if len(parts) >= 3:
        publisher = parts[-1]
        if not year:
            ym = re.search(r'\b((?:19|20)\d{2})\b', publisher)
            if ym:
                year = ym.group(1)
    return authors, venue, year, publisher


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
    pdf = as_http(obj.get('pdf') or '')
    if doi:
        return doi_link(doi), 'doi'
    if href:
        return href, 'href'
    if pdf:
        return pdf, 'pdf'
    return '', ''


def entry(obj: dict, n: int) -> str:
    title = (obj.get('title') or '').strip() or '(无题名)'
    authors, venue, year, publisher = split_authors_line(obj.get('authors_line') or '')
    year = obj.get('year') or year
    cited = obj.get('cited') or ''
    snippet = (obj.get('snippet') or '').strip()
    pdf = as_http(obj.get('pdf') or '')
    link, src = pub_url(obj)
    heading = f'**[{title}]({link})**' if link else f'**{title}**'
    lines = [heading]
    if authors:
        lines.append(f'- 作者：{authors}')
    src_line = venue
    if publisher and publisher.lower() not in (venue or '').lower():
        src_line = f'{venue}（{publisher}）' if venue else publisher
    if src_line:
        lines.append(f'- 来源：{src_line}')
    if year:
        lines.append(f'- 年份：{year}')
    if cited:
        lines.append(f'- Scholar 被引：{cited}')
    if snippet:
        lines.append(f'- 摘要：{snippet}')
    if link:
        if src == 'doi':
            lines.append(f'- 链接：{link}')
        elif src == 'pdf':
            lines.append(f'- 链接：{link}  （检索页无原文 href，用侧栏 PDF 兜底）')
        else:
            lines.append(f'- 链接：{link}')
    else:
        lines.append('- 链接：（未抽出发布页；Scholar 题名无 href，也无侧栏 PDF）')
    if pdf:
        lines.append(f'- PDF：{pdf}')
    else:
        lines.append('- PDF：检索页未见直链（需机构订阅或出版社页）')
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('src')
    p.add_argument('dst')
    p.add_argument('--title', default='谷歌学术文献清单')
    p.add_argument('--theme', default='')
    args = p.parse_args()
    data = json.loads(Path(args.src).read_text(encoding='utf-8'))
    rows = data.get('rows') if isinstance(data, dict) else data
    if not isinstance(rows, list):
        print('输入必须含 rows 数组', file=sys.stderr)
        sys.exit(1)
    query = data.get('query', '') if isinstance(data, dict) else ''
    stats = data.get('stats', '') if isinstance(data, dict) else ''
    chunks = [
        f'# {args.title}',
        '',
        f'> 检索来源：Google Scholar（scholar.google.com）',
        f'> 检索日期：{date.today().isoformat()}',
        f'> 检索式：{query}' if query else '> 检索式：（未记录）',
        f'> Scholar 计数：{stats}' if stats else '',
        '> 说明：题录由检索页抽取（作者行 / 摘要片段 / 被引 / PDF 侧栏）。DOI 需打开原文页或 Crossref 再补。',
        '> 每条均含发布页链接：题名超链接 + 「链接」行（优先 Scholar href，否则侧栏 PDF）。',
    ]
    chunks = [c for c in chunks if c is not None]
    if args.theme:
        chunks += ['', f'主题：{args.theme}']
    chunks.append('')
    for i, obj in enumerate(rows, 1):
        if not isinstance(obj, dict):
            continue
        chunks.append(f'### {i}')
        chunks.append(entry(obj, i))
        chunks.append('')
    Path(args.dst).write_text('\n'.join(chunks).rstrip() + '\n', encoding='utf-8')
    print(f'wrote {len(rows)} entries -> {args.dst}')


if __name__ == '__main__':
    main()
