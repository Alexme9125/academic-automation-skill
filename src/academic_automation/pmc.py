"""Article-scoped access to the current public PMC cloud dataset."""
import json
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode, urlparse, parse_qs

from . import ncbi
from .errors import BrowserError

BUCKET = 'pmc-oa-opendata'
BASE = 'https://' + BUCKET + '.s3.amazonaws.com/'


def versions(pmcid):
    import re
    if not re.fullmatch(r'PMC\d+', pmcid):
        raise BrowserError('Invalid PMCID', 64)
    token, rows = '', []
    while True:
        params = {'list-type': '2', 'prefix': 'metadata/' + pmcid + '.', 'max-keys': 100}
        if token: params['continuation-token'] = token
        try:
            root = ET.fromstring(ncbi.get(BASE + '?' + urlencode(params)))
            for item in root.findall('{*}Contents'):
                key = item.findtext('{*}Key') or ''
                if re.fullmatch(r'metadata/' + pmcid + r'\.\d+\.json', key):
                    rows.append(json.loads(ncbi.get(BASE + quote(key, safe='/'))))
            if root.findtext('{*}IsTruncated') != 'true': return rows
            next_token = root.findtext('{*}NextContinuationToken')
            if not next_token or next_token == token: raise ValueError('Missing continuation token')
            token = next_token
        except (ValueError, ET.ParseError) as exc:
            raise BrowserError('PMC_METADATA_PROTOCOL: retry later', 70, {'retryable': True}) from exc


def select(record, rows, selected=None):
    """No numeric version ranking. Ambiguity needs an explicit human selection."""
    candidates = []
    for row in rows:
        if str(row.get('pmcid', '')).upper() != record['pmcid'].upper(): continue
        if row.get('pmid') and str(row['pmid']) != record['pmid']: continue
        if record.get('doi') and row.get('doi') and row['doi'].lower() != record['doi'].lower(): continue
        from .pdf_verify import norm
        if row.get('title') and record.get('title') and norm(row['title']) != norm(record['title']): continue
        if not row.get('pdf_url'): continue
        candidates.append(row)
    def kind(row):
        value = row.get('is_manuscript')
        if value is False or value == 'no': return 'published'
        if value is True or value == 'yes': return 'author_manuscript'
        return 'unconfirmed'
    published = [r for r in candidates if kind(r) == 'published']
    manuscripts = [r for r in candidates if kind(r) == 'author_manuscript']
    pool = [r for r in candidates if r.get('version') == selected] if selected is not None else published or manuscripts
    if not pool and not candidates: return None
    if len(pool) != 1 or (selected is None and any(kind(r) == 'unconfirmed' for r in candidates)):
        raise BrowserError('PMC_VERSION_AMBIGUOUS: inspect article versions before choosing the main text', 2,
                           {'versions': candidates, 'kind': 'pmc_version'})
    chosen = dict(pool[0])
    parsed = urlparse(chosen['pdf_url'])
    # Only metadata-provided main PDF keys in the documented public bucket.
    import re
    suffix = record['pmcid'] + '.' + str(chosen['version'])
    expected = re.escape('/' + suffix + '/' + suffix + '.pdf')
    if parsed.scheme != 's3' or parsed.netloc != BUCKET or not re.fullmatch(expected, parsed.path):
        raise BrowserError('PMC_UNEXPECTED_PDF_KEY: inspect metadata; no supplement will be substituted', 2,
                           {'kind': 'pmc_version', 'version': chosen})
    chosen['https_url'] = BASE + quote(parsed.path.lstrip('/'), safe='/')
    chosen['md5'] = parse_qs(parsed.query).get('md5', [''])[0]
    chosen['text_version'] = kind(chosen)
    return chosen


def retrieve(version, path):
    from .http_pdf import fetch
    result = fetch(version['https_url'], path, md5=version.get('md5', ''))
    if result.get('status') == 'complete': return True
    if result.get('http_status') in (403, 404, 410) or result.get('error') == 'invalid_pdf_format': return False
    raise BrowserError('PMC_TRANSFER_FAILED: saved partial file and diagnostics; retry this article later', 70,
                       {k: result[k] for k in ('error', 'http_status', 'received_bytes', 'declared_bytes',
                        'retryable', 'diagnostics', 'progress', 'part', 'attempt') if k in result})
