"""DOI resolution, public PDF retrieval and authenticated browser fallbacks."""
import hashlib
import json
import re
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from . import browser_runtime as br, download_watch as dw
from .cnki import pending_path, resume_download, finish_download
from .errors import BrowserError
from .paths import downloads_dir

UA = 'Mozilla/5.0 Chrome/130.0 Safari/537.36'


def resolve_doi(doi):
    url = 'https://doi.org/' + quote(doi, safe='/():')
    try:
        with urlopen(Request(url, headers={'User-Agent': UA}, method='HEAD'), timeout=30) as response:
            return response.url
    except HTTPError as exc:
        if exc.code == 404 and urlparse(exc.url).hostname == 'doi.org':
            raise BrowserError('DOI_UNREGISTERED: ' + doi, 3) from exc
        # A publisher can deny HEAD while allowing the signed-in browser.
        return exc.url
    except (URLError, TimeoutError) as exc:
        raise BrowserError('NETWORK_ERROR resolving DOI: ' + str(exc), 70) from exc


def direct_pdf(url, target):
    # No login cookies are exported into this request. Protected CNKI downloads
    # never pass through this function.
    if not url.startswith(('https://', 'http://')):
        return False
    try:
        with urlopen(Request(url, headers={'User-Agent': UA}), timeout=60) as response:
            head = response.read(8)
            if not head.startswith(b'%PDF-'):
                return False
            with Path(target).open('wb') as output:
                output.write(head)
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    output.write(block)
        return dw.valid_file(target)
    except (HTTPError, URLError, TimeoutError):
        return False


def pdf_candidates(links):
    candidates = []
    for line in links.splitlines():
        if '@@' not in line:
            continue
        label, url = line.split('@@', 1)
        url = url.strip(); low = url.lower(); score = 0
        if not url.startswith(('https://', 'http://')):
            continue
        if '.pdf' in low or '/article/download/' in low or '/uploadfile/' in low:
            score = 4
        if 'pdf' in label.lower():
            score = max(score, 2)
        if re.search(r'/article/view/\d+/\d+', url):
            url = url.replace('/article/view/', '/article/download/', 1)
            score = max(score, 3)
        if 'turkish' in label.lower() or '中文' in label:
            score -= 1
        if score > 0:
            candidates.append((score, url))
    return list(dict.fromkeys(url for _, url in sorted(candidates, key=lambda x: -x[0])))


def host_is(host, suffix):
    return host == suffix or host.endswith('.' + suffix)


def download(doi, dest, name='', retry=False):
    doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi.strip(), flags=re.I)
    if not re.fullmatch(r'10\.\d{4,9}/\S+', doi):
        raise BrowserError('A complete DOI is required', 64)
    name = dw.safe_name(name or doi.replace('/', '_'))
    if not name.lower().endswith('.pdf'):
        name += '.pdf'
    key = hashlib.sha256(('doi\0' + doi.lower() + '\0' + str(Path(dest).resolve()) + '\0' + name).encode()).hexdigest()
    checkpoint = pending_path(dest, key)
    done = resume_download(checkpoint, dest, retry=retry, name=name)
    if done:
        return done
    final = resolve_doi(doi)
    host = (urlparse(final).hostname or '').lower()
    direct = []
    if host_is(host, 'nature.com'):
        match = re.search(r'/articles/([^/?]+)', final)
        if match:
            direct.append('https://www.nature.com/articles/' + match[1] + '.pdf')
    if host_is(host, 'frontiersin.org'):
        direct += ['https://www.frontiersin.org/articles/' + doi + '/pdf',
                   'https://www.frontiersin.org/journals/education/articles/' + doi + '/pdf']
    with tempfile.TemporaryDirectory(prefix='academic-pdf-') as tmp:
        path = Path(tmp) / 'article.pdf'
        for url in direct:
            if direct_pdf(url, path):
                return finish_download(path, dest, checkpoint, {'doi': doi}, name)
        br.navigate(final)
        br.wait_ready('publisher', 25)  # institution proxy redirects may change hostname.
        if host_is(host, 'sagepub.com'):
            links = ['https://journals.sagepub.com/doi/pdf/' + doi + '?download=true']
        elif host_is(host, 'springer.com') or host_is(host, 'springernature.com'):
            links = ['https://link.springer.com/content/pdf/' + quote(doi, safe='/') + '.pdf']
        else:
            script = 'pub/scirp.js' if host_is(host, 'scirp.org') else 'pub/find_pdf.js'
            links = pdf_candidates(br.run_file(script))
        for url in links[:3]:
            if not host_is(host, 'sagepub.com') and direct_pdf(url, path):
                return finish_download(path, dest, checkpoint, {'doi': doi}, name)
    if not links:
        raise BrowserError('NOLINK: publisher page has no identifiable PDF link', 3, {'url': final})
    folder = downloads_dir()
    if not folder.is_dir():
        raise BrowserError('Set --downloads-dir to Chrome\'s actual download directory', 64)
    state = {'status': 'waiting', 'doi': doi, 'downloads': str(folder.resolve()),
             'before': dw.snapshot(folder), 'since': time.time(), 'url': links[0], 'name': name}
    br.atomic_json(checkpoint, state)
    script = (br.DIR / 'pub/jump.js').read_text(encoding='utf-8').replace('__URL__', json.dumps(links[0]))
    br.run_js(script)
    try:
        path = dw.wait_download(folder, state['before'], since=state['since'], timeout=12, page='publisher')
    except BrowserError as exc:
        if exc.code != 4:
            raise
        raise BrowserError('NEEDS_USER: if Chrome displays a PDF, save it into the configured download directory, then repeat this command', 2,
                           {'checkpoint': str(checkpoint), 'downloads': str(folder), 'url': links[0]}) from exc
    return finish_download(path, dest, checkpoint, state, name)
