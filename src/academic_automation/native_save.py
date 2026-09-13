"""One guarded macOS PDF-viewer Save attempt under the caller's browser lock."""
import json
import platform
import re
import time
import uuid
from pathlib import Path, PurePosixPath
from urllib.parse import urldefrag, urlsplit, urlunsplit

from . import browser, browser_runtime as br, download_watch as dw
from .errors import BrowserError
from .paths import SCRIPTS


def needs_user(checkpoint, state, cause):
    native = state.get('native_save', {})
    return BrowserError(
        'NEEDS_USER: native PDF saving did not finish. Keep this article open and save it manually; '
        'if macOS denies UI access, enable Accessibility for the app running the Agent. '
        'Resume after saving; the uncertain download click will not be repeated.', 2,
        {'checkpoint': str(checkpoint), 'native_save': native, 'cause': str(cause),
         'save_folder': native.get('folder', state.get('downloads', ''))})


def recovered_file(state, timeout=3, checkpoint=''):
    """A native Save may outlive osascript. Require a stable, complete staging PDF."""
    native = state.get('native_save')
    if not native or not Path(native['folder']).is_dir():
        return None
    try:
        path = dw.wait_download(native['folder'], {}, since=native['since'], timeout=timeout, interval=.5)
    except BrowserError as exc:
        if exc.code == 4: return None
        raise
    if path.name != native['filename']:
        raise needs_user(checkpoint, state, 'Unexpected filename in the native staging directory')
    return path


def can_retry_preflight(state):
    native = state.get('native_save', {})
    return native.get('status') == 'needs_user' and native.get('phase') == 'preflight' and native.get('events') == []


def same_pdf_target(source, actual):
    if urldefrag(source)[0] == urldefrag(actual)[0]: return True
    original, current = urlsplit(source), urlsplit(actual)
    # Observed Oxford and JAMA article PDF endpoints redirect to Silverchair.
    # Do not accept an arbitrary PDF the user opened in the bound tab meanwhile.
    source_is_article_pdf = (original.netloc == 'academic.oup.com' and '/article-pdf/' in original.path
                            or original.netloc == 'jamanetwork.com' and re.fullmatch(
                                r'/journals/[a-zA-Z0-9_-]+/articlepdf/\d+/[^/]+\.pdf', original.path))
    return (original.scheme == current.scheme == 'https' and bool(source_is_article_pdf)
            and re.fullmatch(r'watermark\d+\.silverchair\.com', current.netloc) is not None
            and PurePosixPath(original.path).name == PurePosixPath(current.path).name
            and current.path.lower().endswith('.pdf'))


def save_pdf(checkpoint, state, url, retry_preflight=False):
    if platform.system() != 'Darwin':
        return None
    if state.get('native_save'):
        recovered = recovered_file(state, checkpoint=checkpoint)
        if recovered: return recovered
        if not (retry_preflight and can_retry_preflight(state)):
            raise needs_user(checkpoint, state, 'Previous native attempt remains unresolved')
        state.setdefault('native_save_attempts', []).append(state.pop('native_save'))
    binding = (br.get_browser().native_binding() if browser.backend_name() == 'extension'
               else browser.read_session())
    if not binding.get('window') or not binding.get('tab'):
        raise needs_user(checkpoint, state, 'No bound Chrome tab; reconnect after inspecting the current article')
    # The same bound tab can legitimately redirect from the article's PDF link
    # to a signed publisher CDN. Read that actual PDF URL; never guess a CDN URL.
    page = json.loads(br.read_js('JSON.stringify({url:location.href,type:document.contentType})'))
    if page.get('type') != 'application/pdf':
        raise needs_user(checkpoint, state, 'The bound tab is not a PDF viewer')
    if not same_pdf_target(url, page['url']):
        raise needs_user(checkpoint, state, 'PDF address changed outside a recognized publisher redirect; inspect this article')
    folder = (Path(checkpoint).parent / (Path(checkpoint).stem + '.native') / uuid.uuid4().hex).resolve()
    folder.mkdir(parents=True)
    request = {**binding, 'url': page['url'], 'folder': str(folder), 'filename': 'received.pdf',
               'backend': browser.backend_name(), 'pdf_type_verified': True}
    request_path = folder / 'request.json'
    br.atomic_json(request_path, request)
    # Persist BEFORE osascript. A crash/timeout must never cause a second click.
    parts = urlsplit(page['url'])
    state['native_save'] = {**request, 'url': url,
        'viewer_location': urlunsplit((parts.scheme, parts.netloc, parts.path, '', '')),
        'since': time.time(), 'status': 'attempted'}
    br.atomic_json(checkpoint, state)
    try:
        raw = browser.run_process(['osascript', '-l', 'JavaScript', str(SCRIPTS / 'macos_pdf_save.js'), str(request_path)], timeout=60)
        result = json.loads(raw)
        if not isinstance(result, dict): raise ValueError('Invalid native save response')
    except (BrowserError, ValueError) as exc:
        result = {'status': 'needs_user', 'error': str(exc), 'phase': 'unknown'}
    finally:
        # A redirected URL may contain a temporary access token. Do not retain it
        # in the checkpoint, diagnostics or staging request after the operation.
        request_path.unlink(missing_ok=True)
    state['native_save'].update(result)
    br.atomic_json(checkpoint, state)
    recovered = recovered_file(state, timeout=12 if result.get('status') in ('save_requested', 'dialog_closed') else 3, checkpoint=checkpoint)
    if not recovered and state.get('downloads'):
        # Chrome may save directly to Downloads without displaying a Save sheet.
        try:
            recovered = dw.wait_download(state['downloads'], state['before'], since=state['since'], timeout=2.5, interval=.5)
        except BrowserError as exc:
            if exc.code != 4: raise
    if recovered:
        state['native_save']['status'] = 'file_verified'
        br.atomic_json(checkpoint, state)
        return recovered
    raise needs_user(checkpoint, state, result.get('error', 'No completed PDF after native Save'))
