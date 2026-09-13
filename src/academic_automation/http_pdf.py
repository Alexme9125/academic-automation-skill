"""Bounded public PDF transfers shared by PMC and publisher downloads."""
import hashlib
import re
import ssl
import time
import uuid
from http.client import HTTPException, HTTPResponse, IncompleteRead
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import browser_runtime as br, download_watch as dw
from .errors import BrowserError


def fetch(url, target, *, opener=None, attempts=3, timeout=30, max_seconds=180, md5=''):
    """Return diagnostics; promote only complete PDFs. Never use browser cookies.

    A strong ETag, total length and local prefix hash are required for resumption.
    Servers ignoring Range cause a fresh file, never concatenation of two copies.
    """
    opener = opener or urlopen
    target = Path(target); target.parent.mkdir(parents=True, exist_ok=True)
    journal = target.with_name(target.name + '.http.json')
    progress = target.with_name(target.name + '.transfer.json')
    history = br.read_json(journal, [])
    deadline = time.monotonic() + max_seconds
    result = {}
    for number in range(attempts):
        saved = br.read_json(progress, {})
        previous = Path(saved.get('part', '.'))
        offset = 0
        if (saved.get('url') == url and saved.get('md5', '') == md5
                and saved.get('etag', '').startswith('"') and saved.get('etag', '').endswith('"')
                and previous.parent.resolve() == target.parent.resolve()
                and previous.name.startswith(target.name + '.') and previous.suffix == '.part'
                and previous.is_file() and not previous.is_symlink()
                and 0 < previous.stat().st_size < (saved.get('declared_bytes') or 0)
                and hashlib.sha256(previous.read_bytes()).hexdigest() == saved.get('prefix_sha256')):
            offset = previous.stat().st_size
        part = previous if offset else target.with_name(target.name + '.' + uuid.uuid4().hex + '.part')
        result = {'url': url, 'part': str(part), 'received_bytes': offset, 'resumed_bytes': offset,
                  'status': 'transferring', 'md5': md5, 'attempt': number + 1}
        if offset: result.update(etag=saved['etag'], declared_bytes=saved['declared_bytes'])
        headers = {'User-Agent': 'Mozilla/5.0 academic-automation', 'Accept-Encoding': 'identity'}
        if offset: headers.update(Range='bytes=' + str(offset) + '-', **{'If-Range': saved['etag']})
        retryable = False

        def publish():
            result['updated_at'] = time.time()
            br.atomic_json(progress, result)

        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise TimeoutError('transfer deadline')
            with opener(Request(url, headers=headers), timeout=min(timeout, remaining)) as response:
                info = getattr(response, 'headers', {})
                status = getattr(response, 'status', 200)
                length = info.get('Content-Length', '')
                length = int(length) if str(length).isdigit() else None
                etag = info.get('ETag', '')
                result.update(http_status=status, etag=etag, declared_bytes=length)
                if offset and status == 200:
                    # A changed resource or server without Range support: retain the prefix.
                    offset = 0; part = target.with_name(target.name + '.' + uuid.uuid4().hex + '.part')
                    result.update(part=str(part), received_bytes=0, resumed_bytes=0)
                valid = status == 200 and not info.get('Content-Range')
                if offset:
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', info.get('Content-Range', ''))
                    valid = bool(status == 206 and match and int(match[1]) == offset
                                 and int(match[2]) == int(match[3]) - 1
                                 and int(match[3]) == saved['declared_bytes']
                                 and length == int(match[2]) - offset + 1 and etag == saved['etag'])
                    result['declared_bytes'] = saved['declared_bytes']
                if not valid or info.get('Content-Encoding', 'identity').lower() != 'identity':
                    result['error'] = 'unexpected_response'
                    # An invalid response cannot re-label an old prefix with a new ETag.
                    result['etag'] = ''
                else:
                    publish()
                    # read1 performs one socket read, allowing the deadline to be checked
                    # even when a peer trickles data continuously below the socket timeout.
                    read = response.read1 if isinstance(response, HTTPResponse) else response.read
                    with part.open('ab' if offset else 'xb') as output:
                        while True:
                            if time.monotonic() >= deadline: raise TimeoutError('transfer deadline')
                            try: block = read(64 * 1024)
                            except IncompleteRead as exc:
                                output.write(exc.partial); output.flush()
                                result['received_bytes'] += len(exc.partial)
                                raise
                            if not block: break
                            output.write(block); output.flush()
                            result['received_bytes'] += len(block)
                            publish()
                    if result['declared_bytes'] is not None and result['received_bytes'] != result['declared_bytes']:
                        result['error'] = 'incomplete_transfer'; retryable = True
                    elif md5 and hashlib.md5(part.read_bytes()).hexdigest() != md5:
                        result['error'] = 'checksum_mismatch'; retryable = True
                    elif not dw.pdf_format(part): result['error'] = 'invalid_pdf_format'
                    else:
                        from .pdf_verify import verify
                        try: result['verification'] = verify(part, {})
                        except BrowserError as exc:
                            result.update(error='invalid_pdf_content', verification=exc.details.get('verification', {}))
                        if not result.get('error'):
                            if target.exists(): target.rename(target.with_name(target.name + '.' + uuid.uuid4().hex + '.previous'))
                            part.replace(target)
                            result['status'] = 'complete'
        except HTTPError as exc:
            result.update(error='http_error', http_status=exc.code)
            retryable = exc.code in (429, 500, 502, 503, 504)
        except (HTTPException, URLError, TimeoutError, ConnectionError, ssl.SSLError):
            result['error'] = 'incomplete_transfer' if result.get('received_bytes') else 'network_error'
            retryable = True
        if time.monotonic() >= deadline and result.get('status') != 'complete':
            result['error'] = 'transfer_deadline'; retryable = True
        if result.get('status') != 'complete': result['status'] = 'failed'
        result['retryable'] = retryable
        if part.is_file(): result['prefix_sha256'] = hashlib.sha256(part.read_bytes()).hexdigest()
        publish(); history.append(dict(result)); br.atomic_json(journal, history)
        if result['status'] == 'complete' or not retryable or time.monotonic() >= deadline: break
        if number + 1 < attempts: time.sleep(min(2 ** number * .5, max(0, deadline - time.monotonic())))
    return {**result, 'diagnostics': str(journal), 'progress': str(progress)}
