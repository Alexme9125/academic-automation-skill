"""Optional PDF content checks; unavailable extraction is never a claimed match."""
import importlib.util
import re
import unicodedata

from .errors import BrowserError

INSTALL = 'python -m pip install -r requirements-pdf.txt'
WARNING = ('正文未自动核验。pypdf 可解析 PDF、读取页数并核对首页题名与作者；'
           '缺少它或无法提取文字时，可能未发现文件损坏、错篇或正文与附录混淆。'
           '可在 Skill 目录执行 ' + INSTALL + '，再核验已有文件，无需重新下载。')


def available():
    return importlib.util.find_spec('pypdf') is not None


def norm(text):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC', text or '')).casefold()


def verify(path, record):
    base = {'content_verified': False, 'pages': None, 'warning': WARNING}
    if not available():
        return dict(base, status='unverified', reason='pypdf_not_installed')
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        count = len(reader.pages)
        if not count:
            raise ValueError('No PDF pages')
    except Exception:
        raise BrowserError('PDF_PARSE_FAILED: the installed PDF parser cannot read this file; inspect or obtain a complete copy', 2,
                           {'verification': dict(base, status='invalid', reason='pdf_parse_failed',
                                                 warning='PDF 解析失败，不能计为合格全文；请核对完整性后重取或提供正确文件。')})
    base['pages'] = count
    try:
        text = reader.pages[0].extract_text() or ''
    except Exception:
        return dict(base, status='unverified', reason='text_extraction_failed',
                    warning='PDF 可解析，但首页文字提取失败，正文题名和作者尚未核验。')
    # A supplement can repeat the article's exact title and author list.
    heading = '\n'.join(text.splitlines()[:12])
    if re.search(r'(?im)^\s*(?:electronic\s+)?(?:supplementary|supplemental|supporting)\s+(?:information|material|appendix|data)\b', heading):
        raise BrowserError('PDF_SUPPLEMENT: this file identifies itself as supplementary material', 2,
                           {'verification': dict(base, status='mismatch', reason='supplement_heading')})
    if len(norm(text)) < 60:
        return dict(base, status='unverified', reason='no_extractable_first_page',
                    warning='PDF 可解析，但首页没有足够可提取文字，正文题名和作者尚未核验。')
    title = norm(record.get('title', ''))
    authors = record.get('authors', [])
    author = record.get('first_author', '') or (authors[0] if authors else '')
    # EFetch records retain the family name separately; never require a CNKI filename suffix.
    family = norm(record.get('first_author_family') or author)
    if not title or not family:
        return dict(base, status='unverified', reason='missing_identity_metadata',
                    warning='PDF 可解析，但缺少可靠题名或作者用于比对，正文身份尚未核验。')
    title_match, author_match = title in norm(text), family in norm(text)
    if not title_match or not author_match:
        raise BrowserError('PDF_IDENTITY_MISMATCH: inspect the first-page title and author before archiving', 2,
                           {'verification': dict(base, status='mismatch', title_verified=title_match, first_author_verified=author_match)})
    return {'status': 'verified', 'content_verified': True, 'title_verified': True,
            'first_author_verified': True, 'pages': count}
