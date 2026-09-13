"""Optional PDF content checks; unavailable extraction is never a claimed match."""
import importlib.util
import re
import unicodedata
import hashlib
import json
from pathlib import Path

from .errors import BrowserError

INSTALL = 'python -m pip install -r requirements-pdf.txt'
WARNING = ('正文未自动核验。pypdf 可解析 PDF、读取页数并核对首页题名与作者；'
           '缺少它或无法提取文字时，可能未发现文件损坏、错篇或正文与附录混淆。'
           '可在 Skill 目录执行 ' + INSTALL + '，再核验已有文件，无需重新下载。')


def available():
    return importlib.util.find_spec('pypdf') is not None


def norm(text):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC', text or '')).casefold()


def identity_key(record):
    return hashlib.sha256(json.dumps({k: record.get(k) for k in
        ('pmid', 'doi', 'title', 'authors', 'first_author', 'first_author_family')},
        ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def approval_matches(path, record, manual):
    return bool(manual and manual.get('sha256') == hashlib.sha256(Path(path).read_bytes()).hexdigest()
                and manual.get('identity_key') == identity_key(record) and manual.get('note') and manual.get('pending_id'))


def verify(path, record, manual=None):
    base = {'content_verified': False, 'pages': None, 'warning': WARNING}
    if not available():
        if approval_matches(path, record, manual):
            return dict(base, status='manually_verified', manually_verified=True, pages=manual.get('pages'),
                        warning='本轮未安装 pypdf，未重新解析；文件摘要与此前人工确认记录一致，保留人工核验状态。')
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
        # A known glyph extraction difference is evidence for review, not an
        # automatic title match. Never equate arbitrary Latin/Greek letters.
        glyph_review = (not title_match and author_match and len(title) >= 20 and 'β' in title
                        and any(title.replace('β', replacement) in norm(text) for replacement in ('b', 'beta')))
        if glyph_review:
            if approval_matches(path, record, manual):
                return dict(base, status='manually_verified', manually_verified=True,
                            title_verified=False, first_author_verified=True,
                            warning='自动题名比对仍有字形差异；用户已核对并确认此摘要对应的文件，计为人工核验。')
            raise BrowserError('PDF_IDENTITY_REVIEW: a possible beta glyph extraction difference needs human review', 2,
                {'kind': 'identity_review', 'verification': dict(base, status='needs_review',
                    reason='possible_beta_glyph_difference', title_verified=False, first_author_verified=True,
                    doi_verified=bool(record.get('doi') and norm(record['doi']) in norm(text)),
                    expected_title=record.get('title'), extracted_excerpt=text[:700],
                    warning='文件可解析，但 β 字形提取差异可能造成题名误报；请核对首页、作者和 DOI，再确认或提供正确文件。')})
        raise BrowserError('PDF_IDENTITY_MISMATCH: inspect the first-page title and author before archiving', 2,
                           {'verification': dict(base, status='mismatch', title_verified=title_match, first_author_verified=author_match)})
    return {'status': 'verified', 'content_verified': True, 'title_verified': True,
            'first_author_verified': True, 'pages': count}
