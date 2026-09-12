#!/usr/bin/env python3
"""Resumable Scholar/WoS searches and CNKI detail extraction, stdlib only."""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from .browser_runtime import (DIR, BrowserError, atomic_json, navigate, read_json,
                             run_file, run_js, wait_ready)


def checkpoint(path, config, refresh=False):
    old = None if refresh else read_json(path)
    if old and old.get('config') == config and old.get('version') == 1:
        return old
    return {'version': 1, 'config': config, 'pages': {}, 'records': {}}


def merge_pages(pages):
    rows, seen = [], set()
    for key in sorted(pages, key=int):
        for row in pages[key].get('rows', []):
            ident = (row.get('ut') or row.get('href') or row.get('title') or '').casefold()
            if ident and ident not in seen:
                seen.add(ident)
                rows.append(row)
    return rows


def collect_wos():
    """Accumulate each viewport so recycled virtual cards cannot discard earlier rows."""
    rows, last_size, stable, expected = {}, -1, 0, 0
    start = time.monotonic()
    last = {}
    for turn in range(35):
        last = json.loads(run_file('wos_rows.js'))
        if last.get('captcha') or last.get('login'):
            raise BrowserError('LOGIN_OR_CAPTCHA', 2)
        for row in last.get('rows', []):
            key = row.get('ut') or row.get('href') or row.get('title')
            if key:
                rows[key] = row
        metrics = json.loads(run_js('''JSON.stringify({slots:document.querySelectorAll('app-record').length,
          bottom:(window.scrollY+window.innerHeight>=document.documentElement.scrollHeight-30),
          listBottom:(function(){var e=document.querySelector('app-records-list');return !e||e.scrollHeight<=e.clientHeight+20||e.scrollTop+e.clientHeight>=e.scrollHeight-30;})()})'''))
        expected = max(expected, metrics['slots'])
        stable = stable + 1 if len(rows) == last_size else 0
        last_size = len(rows)
        # At least the legacy six viewports unless all page slots are observed and stable.
        complete = expected > 0 and len(rows) >= expected and metrics['bottom'] and metrics['listBottom']
        if complete and stable >= 2:
            last.update(rows=list(rows.values()), n=len(rows), complete=True)
            print(f'WOS_COLLECT: {len(rows)} rows, {turn+1} observations, {time.monotonic()-start:.1f}s')
            return last
        if turn >= 5 and metrics['bottom'] and metrics['listBottom'] and stable >= 3 and len(rows) >= expected and rows:
            last.update(rows=list(rows.values()), n=len(rows), complete=True)
            return last
        run_file('wos_scroll.js')
        time.sleep(0.9)
    raise BrowserError(f'INCOMPLETE_WOS_PAGE: collected {len(rows)}, observed slots {expected}; page not checkpointed')


def quoted_query(q):
    q = q.strip()
    return q if (len(q) >= 2 and q[0] == q[-1] == '"') or re.fullmatch(r'[A-Za-z0-9]+', q) else '"' + q.replace('"', '') + '"'


def start_wos(q, oa):
    url = 'https://www.webofscience.com/wos/woscc/basic-search'
    navigate(url)
    wait_ready('wos-basic', 20, url)
    run_file('wos_dismiss.js')
    submit = (DIR / 'wos_submit.js').read_text(encoding='utf-8').replace('__QUERY__', json.dumps(quoted_query(q), ensure_ascii=False))
    status = json.loads(run_js(submit))
    if not status.get('ok'):
        raise BrowserError('SUBMIT_FAILED: ' + str(status))
    ready = wait_ready('wos-results', 25)
    if oa:
        result = json.loads(run_file('wos_oa.js'))
        if not result.get('ok') or not result.get('refine'):
            raise BrowserError('OA_FILTER_FAILED')
        # Refinement can return the same count; require checked filter after settling.
        ready = wait_ready('wos-results', 20, minimum=5)
        checked = run_js("String(!!document.querySelector('input[aria-label^=\"Open Access\"]:checked'))")
        if checked != 'true':
            raise BrowserError('OA_FILTER_NOT_CHECKED')
    return ready['url']


def search(args):
    if args.pages < 1 or (args.mode == 'scholar' and args.pages > 5):
        raise BrowserError('Invalid --pages (Scholar: 1–5)', 64)
    config = {'mode': args.mode, 'query': args.query, 'year': args.year, 'oa': args.oa}
    cp = str(args.output) + '.progress.json'
    state = checkpoint(cp, config, args.refresh)
    if args.mode == 'scholar':
        params = [('hl', 'en'), ('as_sdt', '0,5'), ('q', args.query)]
        if args.year: params.append(('as_ylo', args.year))
        start_url = 'https://scholar.google.com/scholar?' + urlencode(params)
    else:
        start_url = 'https://www.webofscience.com/wos/woscc/basic-search'
    url = start_url
    current = ''
    requested = {}

    def publish():
        rows = merge_pages(requested)
        data = {'query': args.query, 'start_url': start_url, 'n': len(rows), 'rows': rows,
                'stats': next((p.get('stats', '') for p in reversed(list(requested.values()))), ''),
                'complete': len(requested) >= args.pages or bool(requested and not list(requested.values())[-1].get('next'))}
        if args.mode == 'wos':
            data.update(quoted=quoted_query(args.query), summary_url=state.get('summary_url', ''))
        atomic_json(args.output, data)

    # An interrupted new query must not leave an old query's output looking successful.
    publish()

    for page in range(1, args.pages + 1):
        saved = state['pages'].get(str(page))
        if saved:
            requested[str(page)] = saved
            print(f'PAGE {page}: cached n={saved.get("n", 0)}')
        else:
            try:
                if args.mode == 'wos' and not state['pages']:
                    current = start_wos(args.query, args.oa)
                    state['summary_url'] = current
                    url = current
                elif args.mode == 'wos' and page > 1:
                    prev = state['pages'][str(page - 1)]
                    url = re.sub(r'/\d+(?=\?|$)', '/' + str(page), prev['url'])
                    if url == prev['url']:
                        raise BrowserError('Cannot resolve next WoS page; rerun with --refresh')
                if current != url:
                    navigate(url)
                wait_ready('scholar' if args.mode == 'scholar' else 'wos-results', 25, url, minimum=2)
                saved = json.loads(run_file('gs_rows.js')) if args.mode == 'scholar' else collect_wos()
                if saved.get('captcha') or saved.get('login'):
                    raise BrowserError('LOGIN_OR_CAPTCHA', 2)
                if not saved.get('rows'):
                    raise BrowserError('ZERO: no records; empty page not checkpointed')
            except BrowserError:
                publish()
                raise
            state['pages'][str(page)] = saved
            requested[str(page)] = saved
            atomic_json(cp, state)
            print(f'PAGE {page}: n={saved.get("n", 0)}')
        publish()
        if not saved.get('next'):
            break
        url = saved['next'] if args.mode == 'scholar' else url
        current = ''
        if page < args.pages and str(page + 1) not in state['pages']:
            time.sleep(2)  # request pacing is independent of readiness
    print(f'wrote {len(merge_pages(requested))} records -> {args.output}')


def metadata(args):
    urls = list(dict.fromkeys(line.strip() for line in Path(args.query).read_text(encoding='utf-8').splitlines()
                             if line.strip() and not line.lstrip().startswith('#')))
    cp = str(args.output) + '.progress.json'
    # URLs can be appended/reordered without discarding already extracted records.
    script = Path(args.meta_script).resolve()
    import hashlib
    config = {'mode': 'meta', 'script': str(script), 'digest': hashlib.sha256(script.read_bytes()).hexdigest()}
    state = checkpoint(cp, config, args.refresh)
    completed = []
    for url in urls:
        obj = state['records'].get(url)
        if not obj:
            try:
                navigate(url)
                wait_ready('cnki-meta', 25, url, minimum=1.5)
                obj = json.loads(run_js(script.read_text(encoding='utf-8')))
                if not isinstance(obj, dict) or not obj.get('title') or not any(obj.get(k) for k in ('doi', 'authors', 'abstract', 'journal')):
                    raise BrowserError('INCOMPLETE_METADATA: ' + url)
                # Preserve the observed URL rather than relabeling stale content.
                state['records'][url] = obj
                atomic_json(cp, state)
            except BrowserError as exc:
                state.setdefault('errors', {})[url] = {'message': str(exc), 'code': exc.code}
                atomic_json(cp, state)
                atomic_json(args.output, completed)
                raise BrowserError(str(exc), exc.code, {**exc.details, 'failed_url': url,
                    'output': str(Path(args.output).resolve()), 'completed_records': len(completed),
                    'progress': str(Path(cp).resolve())}) from exc
            state.get('errors', {}).pop(url, None)
            atomic_json(cp, state)
            print('META: ' + url)
            time.sleep(2)
        else:
            print('META_CACHED: ' + url)
        completed.append(obj)
        atomic_json(args.output, completed)
    atomic_json(args.output, completed)
    print(f'wrote {len(completed)} records -> {args.output}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['scholar', 'wos', 'meta'])
    ap.add_argument('query'); ap.add_argument('output')
    ap.add_argument('--pages', type=int, default=1); ap.add_argument('--year', default='')
    ap.add_argument('--oa', action='store_true'); ap.add_argument('--refresh', action='store_true')
    ap.add_argument('--meta-script', default=str(DIR / 'cnki_meta.js'))
    args = ap.parse_args()
    from . import cli
    call = ['metadata', args.query, args.output, '--meta-script', args.meta_script] if args.mode == 'meta' else [
        'search', args.mode, args.query, args.output, '--pages', str(args.pages)]
    if args.refresh: call.append('--refresh')
    if args.year: call += ['--year', args.year]
    if args.oa: call.append('--oa')
    sys.exit(cli.main(call))


if __name__ == '__main__':
    main()
