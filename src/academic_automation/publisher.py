"""DOI resolution, public PDF retrieval and authenticated browser fallbacks."""
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from . import browser_runtime as br, download_watch as dw, interaction, access
from .cnki import pending_path, resume_download, finish_download
from .errors import BrowserError
from .paths import downloads_dir
from .doi import normalize as normalize_doi

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
    if links.lstrip().startswith('['):
        rows = json.loads(links)
    else:
        rows = [dict(zip(('label', 'url'), line.split('@@', 1)))
                for line in links.splitlines() if '@@' in line]
    for row in rows:
        label, url = row.get('label', ''), row.get('url', '')
        url = url.strip(); low = url.lower(); score = 0
        if not url.startswith(('https://', 'http://')):
            continue
        # Supplements are valid PDFs too. Never promote them to article full text.
        if (row.get('supplement') or re.search(r'appendix|supplement|supporting (?:info|material)|附录|补充材料', label, re.I)
                or re.search(r'(?:^|[/_.-])(?:app\d+|appendix\w*|supp(?:lement(?:ary)?)?\d*|suppl\w*)\.pdf(?:[?#]|$)', low)):
            continue
        if '.pdf' in low or '/article/download/' in low or '/uploadfile/' in low:
            score = 2
        if 'pdf' in label.lower():
            score = max(score, 5)
        if re.search(r'/pdf(?:[/?#]|$)', low):
            score = max(score, 5)
        if row.get('source') == 'citation_pdf_url':
            score = 8
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
    interaction.require_task()
    return _download(doi, dest, name, retry)


def _download(doi, dest, name='', retry=False):
    doi = normalize_doi(doi)
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
    state = br.read_json(checkpoint, {})
    state.update(doi=doi, source_url=final, name=name, access_policy=access.current())
    return article(final, doi, dest, name, checkpoint, state)


def article(final, doi, dest, name, checkpoint, state, free=False):
    """Publisher fallback shares the calling article's checkpoint and identity."""
    links = state.get('pdf_links', [])
    # Save a snapshot before navigation as login/challenge may interrupt readiness.
    folder = downloads_dir()
    if folder.is_dir() and 'before' not in state:
        state.update(downloads=str(folder.resolve()), before=dw.snapshot(folder), since=time.time())
    state.update(status='waiting', publisher_url=final)
    br.atomic_json(checkpoint, state)
    try:
        return _article(final, doi, dest, name, checkpoint, state, free, links)
    except BrowserError as exc:
        exc.details.update(checkpoint=str(checkpoint), url=state.get('url', final))
        raise


def _article(final, doi, dest, name, checkpoint, state, free, links):
    from .browser import backend_name
    from .download_capture import capture, publisher_control
    host = (urlparse(final).hostname or '').lower()
    direct = []
    if host_is(host, 'nature.com'):
        match = re.search(r'/articles/([^/?]+)', final)
        if match: direct.append('https://www.nature.com/articles/' + match[1] + '.pdf')
    if host_is(host, 'frontiersin.org'):
        direct += ['https://www.frontiersin.org/articles/' + doi + '/pdf',
                   'https://www.frontiersin.org/journals/education/articles/' + doi + '/pdf']
    # Persistent staging lets an identity mismatch or interrupted archive recover.
    path = Path(checkpoint).parent / (Path(checkpoint).stem + '.pdf')
    for url in direct:
        if direct_pdf(url, path):
            state['source_url'] = url
            return finish_download(path, dest, checkpoint, state, name)
    current = json.loads(br.read_js('''JSON.stringify({url:location.href,title:document.title,
      doi:(document.querySelector('meta[name="citation_doi"]')||{}).content||''})'''))
    from .pdf_verify import norm
    expected_title = norm(state.get('record', {}).get('title', ''))
    same_article = (current.get('url') == final or (doi and current.get('doi', '').lower() == doi.lower())
                    or bool(expected_title and expected_title in norm(current.get('title', ''))))
    if not same_article: br.navigate(final)
    br.wait_ready('publisher', 25)
    if not links:
        if host_is(host, 'sagepub.com'):
            links = ['https://journals.sagepub.com/doi/pdf/' + doi + '?download=true']
        elif host_is(host, 'springer.com') or host_is(host, 'springernature.com'):
            links = ['https://link.springer.com/content/pdf/' + quote(doi, safe='/') + '.pdf']
        else:
            script = 'pub/scirp.js' if host_is(host, 'scirp.org') else 'pub/find_pdf.js'
            links = pdf_candidates(br.run_file(script))
    state['pdf_links'] = links; br.atomic_json(checkpoint, state)
    for url in links[:3]:
        if direct_pdf(url, path):
            state['source_url'] = url
            return finish_download(path, dest, checkpoint, state, name)
    if not links:
        if access.public_only():
            result = access.unavailable('No public main PDF identified; availability unknown')
            state.update(result); br.atomic_json(checkpoint, state)
            return {**result, 'checkpoint': str(checkpoint)}
        raise BrowserError('NOLINK: publisher page has no identifiable main-article PDF link; access status remains unknown', 3, {'url': final})
    if access.public_only() and not free:
        # A real page OA marker can establish free access; lack of it is unknown.
        free = br.read_js("String(!!document.querySelector('meta[name=\"citation_open_access\"][content=\"true\"], a[rel=\"license\"][href*=\"creativecommons.org\"]'))") == 'true'
        if not free:
            result = access.unavailable('Public retrieval failed; free access unconfirmed, no subscription request issued')
            state.update(result); br.atomic_json(checkpoint, state)
            return {**result, 'checkpoint': str(checkpoint)}
    folder = downloads_dir()
    if not folder.is_dir(): raise BrowserError("Set --downloads-dir to Chrome's actual download directory", 64)
    # Re-snapshot after any user-authorized retry; file recovery already ran first.
    state.update(status='waiting', downloads=str(folder.resolve()), before=dw.snapshot(folder),
                 since=time.time(), url=links[0], source_url=links[0], name=name)
    br.atomic_json(checkpoint, state)
    if backend_name() == 'extension':
        candidate = capture(checkpoint, state, publisher_control(links[0]))
        if candidate: return finish_download(candidate, dest, checkpoint, state, name)
    else:
        script = (br.DIR / 'pub/jump.js').read_text(encoding='utf-8')
        script = re.sub(r'__URL__|__NAME__', lambda m: json.dumps(links[0] if m[0] == '__URL__' else name), script)
        br.run_js(script)
    try:
        path = dw.wait_download(folder, state['before'], since=state['since'], timeout=12, page='publisher')
    except BrowserError as exc:
        if exc.code not in (2, 4, 70): raise
        raise BrowserError('NEEDS_USER: handle verification or save the displayed PDF, then resume this article', 2,
                           {'checkpoint': str(checkpoint), 'downloads': str(folder), 'url': links[0], 'cause': str(exc)}) from exc
    return finish_download(path, dest, checkpoint, state, name)
