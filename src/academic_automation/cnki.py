"""CNKI browser workflows shared by Windows and macOS."""
import json
import re
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from . import browser_runtime as br, cnki_index as index, download_watch as dw
from . import search_resume as sr, interaction, access
from .paths import downloads_dir
from .errors import BrowserError
from .browser import backend_name

BASE = 'https://kns.cnki.net/kns8s/defaultresult/index?crossids=YSTT4HG0%2CLSTPFY1C%2CEMRPGLPA%2CJUP3MUPD%2CMPMFIG1A%2CWQ0UVIAA%2CBLZOG7CK%2CPWFIRAGL%2CNLBO1Z6R%2CNN3FJMUV&korder='
EXPERT_URL = 'https://kns.cnki.net/kns8s/AdvSearch?type=expert'


def clean(value):
    return re.sub(r'''[《》〈〉“”‘’"'———]''', '', value).strip()


def expert_query(title, author, expert='', affiliation=''):
    affiliation = clean(affiliation)
    if not affiliation:
        return expert
    base = expert or "TI='%s' AND AU='%s'" % (clean(title), clean(author))
    return base + " AND AF='%s'" % affiliation


def start_chinese(title, expert):
    url = EXPERT_URL if expert else BASE + 'TI&kw=' + quote(clean(title))
    br.navigate(url)
    br.wait_ready('cnki-form', 20, url)
    br.run_file('cnki_chinese.js')
    if expert:
        br.wait_ready('expert', 15)
        script = (br.DIR / 'cnki_expert.js').read_text(encoding='utf-8')
        result = br.run_js(script.replace('__EXPR__', json.dumps(expert, ensure_ascii=False)))
        if result != 'searched':
            raise BrowserError('EXPERT_SUBMIT_FAILED: ' + result)
    br.wait_ready('cnki-results', 35, minimum=2)


def page_status():
    state = br.read_file('cnki_page.js')
    if state.startswith('captcha'):
        raise BrowserError('LOGIN_OR_CAPTCHA: complete verification in the connected tab', 2)
    if state.startswith('fee'):
        raise BrowserError('FEE: no download access for this article', 5)
    return state


def locate(title, author, expert='', affiliation='', pages=3, index_path=''):
    query = expert_query(title, author, expert, affiliation)
    cached = index.load_index(index_path, query, pages) if index_path and query else None
    hit = index.select(cached['pages'], title, author) if cached else None
    if hit:
        br.navigate(hit['href'])
        if index.verify_detail(title, author):
            return
    start_chinese(title, query)
    if index_path and query and not cached:
        try:
            data, origin = index.build(index_path, query, pages)
            hit = index.select(data['pages'], title, author)
            if hit:
                br.navigate(hit['href'])
                if index.verify_detail(title, author):
                    return
            start_chinese(title, query)
        except BrowserError as exc:
            if exc.code in (2, 5, 69, 70):
                raise
            start_chinese(title, query)
    matcher = (br.DIR / 'cnki_match.js').read_text(encoding='utf-8')
    values = {'__JSON__': json.dumps(title, ensure_ascii=False), '__AUTHOR__': json.dumps(author, ensure_ascii=False)}
    matcher = re.sub(r'__JSON__|__AUTHOR__', lambda match: values[match.group()], matcher)
    for number in range(max(1, pages)):
        # Select in a read-only evaluation, then navigate outside that context.
        # The legacy snippet keeps its original navigation behavior for old callers.
        result = br.read_js('(function(){var __academicSelectOnly=true;return ' + matcher + '\n})()')
        if result.startswith('captcha'):
            raise BrowserError('CAPTCHA', 2)
        if '@@MATCH@@' in result:
            selected = json.loads(result.split('@@MATCH@@', 1)[1])
            br.navigate(selected['href'])
            br.wait_ready('cnki-meta', 25)
            if not page_status().startswith('detail'):
                raise BrowserError('NODETAIL: matched result did not reach the detail page')
            if not index.verify_detail(selected['title'], author):
                raise BrowserError('DETAIL_IDENTITY_MISMATCH: verify the selected title and author', 1)
            return
        if number + 1 < pages:
            previous = br.wait_ready('cnki-results', 15)['signature']
            if not br.run_file('cnki_next.js').startswith('next'):
                break
            br.wait_ready('cnki-results', 20, previous=previous, minimum=2)
    raise BrowserError('NOMATCH_OR_AMBIGUOUS: no unique title and author match')


def pending_path(dest, key):
    return Path(dest).resolve() / '.academic-downloads' / (key + '.json')


def finish_download(path, dest, checkpoint, state, name=''):
    from .cnki_batch import file_record
    import hashlib
    # Record the candidate before moving it so a crash cannot trigger another click.
    state.update(candidate=str(Path(path).resolve()), status='archiving',
                 candidate_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
    br.atomic_json(checkpoint, state)
    verify_download(path, checkpoint, state)
    def journal(target):
        state['archive_target'] = str(target)
        br.atomic_json(checkpoint, state)
    saved = dw.archive(path, dest, name or state.get('name', ''), journal=journal)
    state.update(status='complete', file=file_record(saved), sha256=state['candidate_sha256'])
    br.atomic_json(checkpoint, state)
    return download_result(state, checkpoint)


def verify_download(path, checkpoint, state):
    from .pdf_verify import verify
    try:
        if not dw.valid_file(path):
            raise BrowserError('INVALID_DOWNLOAD: file is incomplete or has an invalid format', 2,
                               {'verification': {'status': 'invalid', 'reason': 'incomplete_or_invalid_format'}})
        if Path(path).suffix.lower() == '.pdf':
            record = state.get('record') or {'title': state.get('title', ''), 'first_author': state.get('author', '')}
            state['verification'] = (verify(path, record, state['manual_identity']) if state.get('manual_identity')
                                     else verify(path, record))
        else:
            state['verification'] = {'status': 'unverified', 'content_verified': False, 'reason': 'caj_format'}
    except BrowserError as exc:
        state['verification'] = exc.details.get('verification', {})
        exc.details.update(checkpoint=str(checkpoint), path=str(path))
        if exc.details.get('kind') == 'identity_review':
            import hashlib
            exc.details['sha256'] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if state['verification'].get('status') == 'invalid': exc.details['kind'] = 'invalid_file'
        br.atomic_json(checkpoint, state)
        raise


def reject_invalid_for_retry(path, checkpoint, state, retry):
    try:
        verify_download(path, checkpoint, state)
    except BrowserError as exc:
        if not retry or exc.details.get('kind') != 'invalid_file': raise
        # The CLI only supplies retry after an actual reply. Keep the old file,
        # and retain its diagnosis, before allowing a fresh bounded request.
        state.setdefault('rejected_files', []).append({'path': str(path), 'verification': state['verification']})
        for key in ('file', 'sha256', 'archive_target', 'candidate', 'candidate_sha256', 'transfer_file',
                    'download_event', 'native_save', 'verification', 'manual_identity', 'publisher_stage'):
            state.pop(key, None)
        state['status'] = 'retry_ready'
        br.atomic_json(checkpoint, state)
        return True
    return False


def download_result(state, checkpoint, cached=False):
    return {'path': state['file']['path'], 'checkpoint': str(checkpoint), 'status': 'complete', 'cached': cached,
            **{k: state[k] for k in ('file', 'sha256', 'source_url', 'provenance', 'text_version', 'verification', 'manual_identity', 'access_policy', 'pmid', 'record', 'download_route', 'rejected_files', 'http_diagnostics') if k in state}}


def resume_download(checkpoint, dest, author='', retry=False, name=''):
    from .cnki_batch import file_record
    import hashlib
    state = br.read_json(checkpoint, {})
    saved = state.get('file', {}).get('path')
    if state.get('status') == 'complete' and saved and Path(saved).exists():
        stat = Path(saved).stat()
        if any(state['file'].get(k) != v for k, v in {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}.items()):
            raise BrowserError('ARCHIVED_FILE_CHANGED: inspect the existing file before requesting another copy', 2,
                               {'checkpoint': str(checkpoint), 'path': saved})
        if state.get('sha256') and hashlib.sha256(Path(state['file']['path']).read_bytes()).hexdigest() != state['sha256']:
            raise BrowserError('ARCHIVED_FILE_CHANGED: inspect the existing file before retrying', 2, {'checkpoint': str(checkpoint)})
        if reject_invalid_for_retry(saved, checkpoint, state, retry): return None
        br.atomic_json(checkpoint, state)
        return download_result(state, checkpoint, True)
    if state.get('status') in ('waiting', 'archiving'):
        target = state.get('archive_target')
        if target and dw.valid_file(target) and hashlib.sha256(Path(target).read_bytes()).hexdigest() == state.get('candidate_sha256'):
            if reject_invalid_for_retry(target, checkpoint, state, retry): return None
            state.update(status='complete', file=file_record(target))
            state['sha256'] = state['candidate_sha256']
            br.atomic_json(checkpoint, state)
            return {**download_result(state, checkpoint, True), 'path': target}
        candidate = state.get('candidate')
        if candidate and Path(candidate).exists():
            if reject_invalid_for_retry(candidate, checkpoint, state, retry): return None
            return finish_download(candidate, dest, checkpoint, state, name)
        if state.get('native_save'):
            from .native_save import recovered_file
            candidate = recovered_file(state, checkpoint=checkpoint)
            if candidate:
                state['native_save']['status'] = 'file_verified'
                return finish_download(candidate, dest, checkpoint, state, name)
        if 'downloads' in state:
            try:
                candidate = dw.wait_download(state['downloads'], state['before'], author,
                                             state['since'], timeout=2.5, interval=.5)
                state.setdefault('download_route', backend_name() + '_downloads_folder')
                return finish_download(candidate, dest, checkpoint, state, name)
            except BrowserError as exc:
                if exc.code != 4:
                    raise
        if state.get('native_save'):
            from .native_save import needs_user, can_retry_preflight, save_pdf
            if retry and can_retry_preflight(state):
                candidate = save_pdf(checkpoint, state, state['native_save']['url'], retry_preflight=True)
                if candidate: return finish_download(candidate, dest, checkpoint, state, name)
            raise needs_user(checkpoint, state, 'Previous native Save remains unresolved; inspect its dialog or saved file')
        if not retry:
            raise BrowserError('NEEDS_USER: save the PDF/CAJ, then repeat this command; use --retry only to issue a new request', 2,
                               {'checkpoint': str(checkpoint), 'downloads': state.get('downloads', '')})
        if state.get('transfer_file') and Path(state['transfer_file']).exists():
            raise BrowserError('NEEDS_USER: an unconfirmed browser transfer exists; inspect it or save the paper manually before retrying', 2,
                               {'checkpoint': str(checkpoint), 'transfer_file': state['transfer_file']})
        if state.get('publisher_url') and state.get('url') and 'publisher_stage' not in state:
            state['publisher_stage'] = 'pdf_requested'
            br.atomic_json(checkpoint, state)
    return None


def extension_download(checkpoint, state, author):
    """Save the event-owned file independently of Chrome's default download folder."""
    probe = (br.DIR / 'cnki_download_probe.js').read_text(encoding='utf-8')
    selected = None
    for attempt in range(3):
        page_status()
        selected = json.loads(br.read_js(probe.replace('__TOKEN__', json.dumps(uuid.uuid4().hex))))
        if selected['status'] != 'no_link':
            break
        if attempt < 2: time.sleep(2)
    state['download_control'] = selected
    br.atomic_json(checkpoint, state)
    if selected['status'] == 'no_link':
        state['status'] = 'no_link'; br.atomic_json(checkpoint, state)
        raise BrowserError('NOLINK: no visible PDF/CAJ control found', 3, {'checkpoint': str(checkpoint)})
    if selected['status'] != 'selected':
        raise BrowserError('NEEDS_USER: more than one visible download control; inspect this article', 2,
                           {'checkpoint': str(checkpoint)})
    from .download_capture import capture
    return capture(checkpoint, state, selected['selector'], author)


def download(title, author, dest, expert='', affiliation='', pages=3, index_path='', retry=False):
    interaction.require_task()
    return _download(title, author, dest, expert, affiliation, pages, index_path, retry)


def _download(title, author, dest, expert='', affiliation='', pages=3, index_path='', retry=False):
    from .cnki_batch import identity, existing_exact
    if not title.strip() or not author.strip():
        raise BrowserError('NEED_AUTHOR: Chinese downloads require title and first author before opening the browser', 64)
    if pages < 0:
        raise BrowserError('Invalid --pages', 64)
    checkpoint = pending_path(dest, identity(title, author, dest))
    completed = resume_download(checkpoint, dest, author, retry)
    if completed:
        return completed
    found = existing_exact(title, author, dest)
    previous = br.read_json(checkpoint, {})
    rejected = {str(Path(item['path']).resolve()) for item in previous.get('rejected_files', [])}
    if found and str(Path(found).resolve()) not in rejected and previous.get('status') != 'complete':
        return {**finish_download(found, dest, checkpoint, {**previous, 'title': title, 'author': author}), 'cached': True}
    folder = downloads_dir()
    if not folder.is_dir():
        raise BrowserError('Set --downloads-dir to Chrome\'s actual download directory', 64)
    locate(title, author, expert, affiliation, pages, index_path)
    state = {**br.read_json(checkpoint, {}), 'status': 'waiting', 'title': title, 'author': author,
             'downloads': str(folder.resolve()), 'before': dw.snapshot(folder), 'since': time.time()}
    br.atomic_json(checkpoint, state)
    if backend_name() == 'extension':
        candidate = extension_download(checkpoint, state, author)
        if candidate:
            state['download_route'] = 'extension_event'
            return finish_download(candidate, dest, checkpoint, state)
        # No event may mean Chrome handled the download itself. Check the original
        # snapshot first; a missing event never authorizes a second click.
        try:
            candidate = dw.wait_download(folder, state['before'], author, state['since'],
                                         timeout=max(1, 40 - (time.time() - state['since'])), page=True)
        except BrowserError as exc:
            if exc.code not in (2, 4, 70): raise
            raise BrowserError('NEEDS_USER: inspect the current page or save the PDF; do not repeat the click automatically', 2,
                               {'checkpoint': str(checkpoint), 'downloads': str(folder),
                                'diagnostics': state.get('download_event'), 'cause': str(exc)}) from exc
        state['download_route'] = 'extension_downloads_folder'
        return finish_download(candidate, dest, checkpoint, state)
    for attempt in range(3):
        result = br.run_file('cnki_click.js')  # location.href preserves CNKI referrer.
        if result.startswith('captcha'):
            raise BrowserError('CAPTCHA: complete verification, then repeat the command', 2, {'checkpoint': str(checkpoint)})
        if result.startswith('fee'):
            state['status'] = 'fee'; br.atomic_json(checkpoint, state)
            raise BrowserError('FEE: no download access', 5)
        if not result.startswith('nolink'):
            break
        time.sleep(2)
    if result.startswith('nolink'):
        state['status'] = 'no_link'; br.atomic_json(checkpoint, state)
        raise BrowserError('NOLINK: detail page has no PDF/CAJ link', 3)
    try:
        candidate = dw.wait_download(folder, state['before'], author, state['since'], timeout=40, page=True)
    except BrowserError as exc:
        if exc.code in (2, 4, 70):
            raise BrowserError('NEEDS_USER: inspect verification or save the current download in Chrome', 2,
                {'checkpoint': str(checkpoint), 'downloads': str(folder), 'cause': str(exc)}) from exc
        raise
    return finish_download(candidate, dest, checkpoint, state)


def chinese_search(query, output, pages=1, refresh=False, expert=False):
    interaction.require_task()
    if pages < 1 or not query.strip():
        raise BrowserError('Chinese search requires a query and --pages >= 1', 64)
    expression = query.strip() if expert else "SU='%s'" % clean(query)
    config = {'mode': 'cnki-chinese', 'query': query, 'expert': expert}
    cp = str(output) + '.progress.json'
    state = sr.checkpoint(cp, config, refresh)

    def publish(complete=False):
        selected = {k: v for k, v in state['pages'].items() if int(k) <= pages}
        rows = sr.merge_pages(selected)
        result = {'database': 'cnki-chinese', 'query': query, 'expert_query': expression,
                  'total': state.get('total'), 'n': len(rows), 'rows': rows, 'complete': complete}
        br.atomic_json(output, result)
        return result

    if len(state['pages']) >= pages or state.get('exhausted'):
        return publish(True)
    publish()
    start_chinese('', expression)
    count = json.loads(br.read_file('cnki_count.js')).get('n')
    if count is None:
        raise BrowserError('INCOMPLETE_CNKI_COUNT: result count is unavailable', 70, {'retryable': True})
    state['total'] = count
    if count == 0:
        state['exhausted'] = True; br.atomic_json(cp, state)
        return publish(True)
    for number in range(1, pages + 1):
        ready = br.wait_ready('cnki-results', 25, minimum=2)
        data = json.loads(br.read_file('cnki_rows.js'))
        if not data.get('rows'):
            raise BrowserError('INCOMPLETE_CNKI_PAGE', 70, {'retryable': True, 'page': number})
        state['pages'][str(number)] = data
        br.atomic_json(cp, state)
        result = publish(number == pages)
        if number == pages: return result
        if not br.run_file('cnki_next.js').startswith('next'):
            state['exhausted'] = True; br.atomic_json(cp, state)
            return publish(True)
        br.wait_ready('cnki-results', 20, previous=ready['signature'], minimum=2)
        time.sleep(2)


def foreign_search(query, output, pages=1, refresh=False):
    interaction.require_task()
    return _foreign_search(query, output, pages, refresh)


def _foreign_search(query, output, pages=1, refresh=False):
    if pages < 1:
        raise BrowserError('Invalid --pages', 64)
    config = {'mode': 'cnki-foreign', 'query': query}
    if access.current(): config['access_policy'] = access.current()
    cp = str(output) + '.progress.json'
    state = sr.checkpoint(cp, config, refresh)
    if len(state['pages']) >= pages or state.get('exhausted'):
        selected = {k: v for k, v in state['pages'].items() if int(k) <= pages}
        result = {'query': query, 'total': state.get('total'), 'rows': sr.merge_pages(selected), 'complete': True}
        result['n'] = len(result['rows']); access.classify(result); br.atomic_json(output, result)
        return result
    br.atomic_json(output, access.classify({'query': query, 'rows': sr.merge_pages(state['pages']), 'complete': False}))
    quoted = sr.quoted_query(query)
    url = BASE + 'SU&kw=' + quote(quoted)
    br.navigate(url); br.wait_ready('cnki-form', 20, url)
    br.run_js('''(function(){var e=document.getElementById('txt_search')||document.querySelector('input.search-input');
if(!e)return 'missing';Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,QUERY);
e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return 'set';})()'''.replace('QUERY', json.dumps(quoted)))
    if br.run_file('cnki_foreign.js').startswith('notfound'):
        raise BrowserError('NO_FOREIGN_TAB')
    br.wait_ready('cnki-results', 25, minimum=2)
    count = json.loads(br.run_file('cnki_count.js')).get('n') or 0
    if count > 50000:
        raise BrowserError('PHRASE_TOO_BROAD: narrow the query', 64)
    if count == 0:
        raise BrowserError('ZERO: no search results')
    state['total'] = count
    for number in range(1, pages + 1):
        ready = br.wait_ready('cnki-results', 25, minimum=2)
        data = json.loads(br.run_file('cnki_rows.js'))
        if not data.get('rows'):
            raise BrowserError('INCOMPLETE_CNKI_PAGE')
        state['pages'][str(number)] = data
        br.atomic_json(cp, state)
        result = {'query': query, 'total': count, 'rows': sr.merge_pages({k:v for k,v in state['pages'].items() if int(k)<=number}), 'complete': number == pages}
        result['n'] = len(result['rows']); access.classify(result); br.atomic_json(output, result)
        if number == pages:
            break
        if not br.run_file('cnki_next.js').startswith('next'):
            state['exhausted'] = True; br.atomic_json(cp, state)
            result['complete'] = True; br.atomic_json(output, result)
            break
        br.wait_ready('cnki-results', 20, previous=ready['signature'], minimum=2)
        time.sleep(2)
    return result
