#!/usr/bin/env python3
"""Backend-neutral runtime and bounded readiness waits."""
import argparse
import json
import sys
import time
from pathlib import Path

from .paths import SCRIPTS as DIR


from .errors import BrowserError
from .browser import get_browser


def run_js(js):
    return get_browser().evaluate(js)


def run_file(name):
    return run_js((DIR / name).read_text(encoding='utf-8'))


def navigate(url):
    return get_browser().navigate(url)


def atomic_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    import os
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=str(path.parent))
    tmp = Path(temporary)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(obj, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def wait_ready(mode, timeout=20, url='', previous='', minimum=1.0):
    js = (DIR / 'browser_ready.js').read_text(encoding='utf-8').replace(
        '__OPTIONS__', json.dumps({'mode': mode, 'url': url}))
    start = time.monotonic()
    last, stable_since, state = None, start, {}
    while time.monotonic() - start < timeout:
        state = json.loads(run_js(js))
        if state.get('captcha') or state.get('login'):
            raise BrowserError('LOGIN_OR_CAPTCHA: complete verification in Chrome', 2, {'url': state.get('url', '')})
        if state.get('not_found'):
            raise BrowserError('PAGE_NOT_FOUND: refresh the source link for the same article', 3, {'url': state.get('url', '')})
        if state.get('fee'):
            raise BrowserError('FEE: institution has no download access', 5)
        fingerprint = state.get('signature')
        now = time.monotonic()
        if fingerprint != last or not state.get('ready'):
            last, stable_since = fingerprint, now
        floor = max(minimum, 8 if state.get('empty') else minimum)
        if (state.get('ready') and (not previous or fingerprint != previous)
                and now - start >= floor and now - stable_since >= 1):
            print(f'READY {mode}: {now-start:.1f}s', file=sys.stderr)
            return state
        time.sleep(0.5)
    raise BrowserError(f'WAIT_TIMEOUT {mode}: {state.get("url", "")}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode')
    ap.add_argument('--timeout', type=float, default=20)
    ap.add_argument('--url', default='')
    ap.add_argument('--previous', default='')
    ap.add_argument('--minimum', type=float, default=1)
    args = ap.parse_args()
    try:
        state = wait_ready(args.mode, args.timeout, args.url, args.previous, args.minimum)
        print(state['signature'])
    except BrowserError as e:
        print(str(e), file=sys.stderr)
        sys.exit(e.code)


if __name__ == '__main__':
    main()
