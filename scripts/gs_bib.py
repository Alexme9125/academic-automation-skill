#!/usr/bin/env python3
# 把 gs_search.sh 的 JSON 写成文献目录 Markdown。
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

def entry(obj: dict, n: int) -> str:
    title = (obj.get('title') or '').strip() or '(无题名)'
    authors, venue, year, publisher = split_authors_line(obj.get('authors_line') or '')
    year = obj.get('year') or year
    cited = obj.get('cited') or ''
    snippet = (obj.get('snippet') or '').strip()
    href = (obj.get('href') or '').strip()
    pdf = (obj.get('pdf') or '').strip()
    lines = [f'**{title}**']
    if authors:
        lines.append(f'- 作者：{authors}')
    src = venue
    if publisher and publisher.lower() not in (venue or '').lower():
        src = f'{venue}（{publisher}）' if venue else publisher
    if src:
        lines.append(f'- 来源：{src}')
    if year:
        lines.append(f'- 年份：{year}')
    if cited:
        lines.append(f'- Scholar 被引：{cited}')
    if snippet:
        lines.append(f'- 摘要：{snippet}')
    if href:
        lines.append(f'- 链接：{href}')
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
