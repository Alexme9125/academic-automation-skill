#!/usr/bin/env python3
# 把 metaloop 的 JSON 数组写成外文题录清单 Markdown。
# 每条必须含发布页超链接（题名 [题名](url) + 链接/全文行）。
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
    """Return (url, source) from doi / url / href / pdf. source is doi|cnki|href|pdf|''."""
    doi = (obj.get('doi') or obj.get('doi_header') or '').strip()
    page = as_http(obj.get('url') or '') or as_http(obj.get('href') or '') or as_http(obj.get('link') or '')
    pdf = as_http(obj.get('pdf') or '')
    if doi:
        return doi_link(doi), 'doi'
    if page:
        return page, 'cnki' if 'cnki.net' in page.lower() or 'kcms2' in page.lower() else 'href'
    if pdf:
        return pdf, 'pdf'
    return '', ''


def entry(obj: dict) -> str:
    title = (obj.get('title') or '').strip() or '(无题名)'
    authors = (obj.get('authors') or '').strip() or '（未提取）'
    journal = (obj.get('journal') or '').strip()
    year = (obj.get('year') or '').strip()
    doi = (obj.get('doi') or obj.get('doi_header') or '').strip()
    abstract = (obj.get('abstract') or '').strip()
    link, src = pub_url(obj)
    heading = f'**[{title}]({link})**' if link else f'**{title}**'
    src_line = journal
    if year and year not in src_line:
        src_line = f'{src_line}, {year}' if src_line else year
    lines = [heading, f'- 作者：{authors}']
    if src_line:
        lines.append(f'- 期刊：{src_line}')
    if doi:
        lines.append(f'- DOI：{doi}')
    if link:
        if src == 'doi':
            lines.append(f'- 全文：{link}  （先按出版社路由尝试 OA；失败则标机构订阅）')
        elif src == 'cnki':
            lines.append(f'- 链接：{link}  （知网摘要页；无 DOI）')
        elif src == 'pdf':
            lines.append(f'- 链接：{link}  （无发布页 URL，用 PDF 兜底）')
        else:
            lines.append(f'- 链接：{link}')
    else:
        lines.append('- 链接：（未抽出发布页；请补 DOI 或知网 kcms2 摘要 URL）')
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
        '> 每条均含发布页链接：题名超链接 + 「全文」或「链接」行（优先 https://doi.org/{DOI}，否则知网摘要页）。',
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
