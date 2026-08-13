#!/usr/bin/env python3
# 把 metaloop 的 JSON 数组写成外文题录清单 Markdown。
# 用法: cnki_bib.py in.json out.md [--title "清单标题"] [--theme "主题说明"]
import argparse, json, sys
from pathlib import Path

def first_author(authors: str) -> str:
    if not authors:
        return ''
    for sep in (';', '；', ',', '，'):
        if sep in authors:
            return authors.split(sep)[0].strip()
    return authors.strip().split()[0] if authors.strip() else ''

def entry(obj: dict) -> str:
    title = (obj.get('title') or '').strip() or '(无题名)'
    authors = (obj.get('authors') or '').strip() or '（未提取）'
    journal = (obj.get('journal') or '').strip()
    year = (obj.get('year') or '').strip()
    doi = (obj.get('doi') or obj.get('doi_header') or '').strip()
    abstract = (obj.get('abstract') or '').strip()
    url = (obj.get('url') or '').strip()
    src = journal
    if year and year not in src:
        src = f'{src}, {year}' if src else year
    lines = [f'**{title}**', f'- 作者：{authors}']
    if src:
        lines.append(f'- 期刊：{src}')
    if doi:
        lines.append(f'- DOI：{doi}')
        lines.append(f'- 全文：https://doi.org/{doi}  （先按出版社路由尝试 OA；失败则标机构订阅）')
    elif url:
        lines.append(f'- 知网详情：{url}')
        lines.append('- 全文：无 DOI，仅题录')
    else:
        lines.append('- 全文：无 DOI，仅题录')
    if abstract:
        lines.append(f'- 摘要：{abstract}')
    return '\n'.join(lines)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('src')
    p.add_argument('dst')
    p.add_argument('--title', default='外文文献清单')
    p.add_argument('--theme', default='')
    args = p.parse_args()
    data = json.loads(Path(args.src).read_text(encoding='utf-8'))
    if isinstance(data, dict) and 'rows' in data:
        data = data['rows']
    if not isinstance(data, list):
        print('输入必须是 JSON 数组', file=sys.stderr)
        sys.exit(1)
    chunks = [
        f'# {args.title}',
        '',
        '> 检索来源：中国知网·外文库（kns.cnki.net）。外文库只提供题录 + 摘要 + DOI，不提供 PDF/CAJ 下载。',
        '> OA 文献按 DOI 走出版社获取；付费文献走机构订阅。DOI 以详情页最长候选为准（知网头部常截断）。',
    ]
    if args.theme:
        chunks += ['', f'主题：{args.theme}']
    chunks.append('')
    for i, obj in enumerate(data, 1):
        if not isinstance(obj, dict):
            continue
        chunks.append(f'### {i}')
        chunks.append(entry(obj))
        chunks.append('')
    Path(args.dst).write_text('\n'.join(chunks).rstrip() + '\n', encoding='utf-8')
    print(f'wrote {len(data)} entries -> {args.dst}')

if __name__ == '__main__':
    main()
