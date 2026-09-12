"""CNKI browser workflows shared by Windows and macOS."""
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

from . import browser_runtime as br, cnki_index as index, download_watch as dw
from . import search_resume as sr
from .paths import downloads_dir
from .errors import BrowserError

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
    state = br.run_file('cnki_page.js')
    if state.startswith('captcha'):
        raise BrowserError('CAPTCHA: complete verification in the connected tab', 2)
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
        result = br.run_js(matcher)
        if result.startswith('captcha'):
            raise BrowserError('CAPTCHA', 2)
        if '@@MATCH@@' in result:
            br.wait_ready('cnki-meta', 25)
            if not page_status().startswith('detail'):
                raise BrowserError('NODETAIL: matched result did not reach the detail page')
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
    def journal(target):
        state['archive_target'] = str(target)
        br.atomic_json(checkpoint, state)
    saved = dw.archive(path, dest, name, journal=journal)
    state.update(status='complete', file=file_record(saved))
    br.atomic_json(checkpoint, state)
    return {'path': str(saved), 'checkpoint': str(checkpoint), 'status': 'complete'}


def resume_download(checkpoint, dest, author='', retry=False, name=''):
    from .cnki_batch import verified, file_record
    import hashlib
    state = br.read_json(checkpoint, {})
    if state.get('status') == 'complete' and verified(state.get('file')):
        return {'path': state['file']['path'], 'checkpoint': str(checkpoint), 'status': 'complete', 'cached': True}
    if state.get('status') in ('waiting', 'archiving'):
        target = state.get('archive_target')
        if target and dw.valid_file(target) and hashlib.sha256(Path(target).read_bytes()).hexdigest() == state.get('candidate_sha256'):
            state.update(status='complete', file=file_record(target))
            br.atomic_json(checkpoint, state)
            return {'path': target, 'checkpoint': str(checkpoint), 'status': 'complete', 'cached': True}
        candidate = state.get('candidate')
        if candidate and dw.valid_file(candidate):
            return finish_download(candidate, dest, checkpoint, state, name)
        if 'downloads' in state:
            try:
                candidate = dw.wait_download(state['downloads'], state['before'], author,
                                             state['since'], timeout=2.5, interval=.5)
                return finish_download(candidate, dest, checkpoint, state, name)
            except BrowserError as exc:
                if exc.code != 4:
                    raise
        if not retry:
            raise BrowserError('NEEDS_USER: save the PDF/CAJ, then repeat this command; use --retry only to issue a new request', 2,
                               {'checkpoint': str(checkpoint), 'downloads': state.get('downloads', '')})
    return None


def download(title, author, dest, expert='', affiliation='', pages=3, index_path='', retry=False):
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
    if found and not br.read_json(checkpoint, {}).get('status') == 'complete':
        return {'path': str(found.resolve()), 'status': 'complete', 'cached': True}
    folder = downloads_dir()
    if not folder.is_dir():
        raise BrowserError('Set --downloads-dir to Chrome\'s actual download directory', 64)
    locate(title, author, expert, affiliation, pages, index_path)
    state = {'status': 'waiting', 'title': title, 'author': author,
             'downloads': str(folder.resolve()), 'before': dw.snapshot(folder), 'since': time.time()}
    br.atomic_json(checkpoint, state)
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
        if exc.code in (2, 4):
            raise BrowserError('NEEDS_USER: inspect verification or save the current download in Chrome', 2,
                {'checkpoint': str(checkpoint), 'downloads': str(folder), 'cause': str(exc)}) from exc
        raise
    return finish_download(candidate, dest, checkpoint, state)


def foreign_search(query, output, pages=1, refresh=False):
    if pages < 1:
        raise BrowserError('Invalid --pages', 64)
    config = {'mode': 'cnki-foreign', 'query': query}
    cp = str(output) + '.progress.json'
    state = sr.checkpoint(cp, config, refresh)
    if len(state['pages']) >= pages or state.get('exhausted'):
        selected = {k: v for k, v in state['pages'].items() if int(k) <= pages}
        result = {'query': query, 'total': state.get('total'), 'rows': sr.merge_pages(selected), 'complete': True}
        result['n'] = len(result['rows']); br.atomic_json(output, result)
        return result
    br.atomic_json(output, {'query': query, 'rows': sr.merge_pages(state['pages']), 'complete': False})
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
        result['n'] = len(result['rows']); br.atomic_json(output, result)
        if number == pages:
            break
        if not br.run_file('cnki_next.js').startswith('next'):
            state['exhausted'] = True; br.atomic_json(cp, state)
            result['complete'] = True; br.atomic_json(output, result)
            break
        br.wait_ready('cnki-results', 20, previous=ready['signature'], minimum=2)
        time.sleep(2)
    return result
