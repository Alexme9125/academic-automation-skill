#!/usr/bin/env python3
"""Small Apple Events runtime; bounded readiness waits, no CDP/session export."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent


class BrowserError(RuntimeError):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


def run_js(js):
    script = '''on run argv
tell application "Google Chrome"
return execute active tab of front window javascript (item 1 of argv)
end tell
end run'''
    try:
        r = subprocess.run(['osascript', '-e', script, js], capture_output=True,
                           text=True, timeout=15)
    except subprocess.TimeoutExpired as e:
        raise BrowserError('Apple Events timed out; check Chrome permission/dialogs') from e
    if r.returncode:
        raise BrowserError(r.stderr.strip() or r.stdout.strip())
    return r.stdout.strip()


def run_file(name):
    return run_js((DIR / name).read_text(encoding='utf-8'))


def navigate(url):
    r = subprocess.run([str(DIR / 'macos_chrome_nav.sh'), url], timeout=35)
    if r.returncode:
        raise BrowserError('Navigation failed')


def atomic_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


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
            raise BrowserError('LOGIN_OR_CAPTCHA: complete verification in Chrome', 2)
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
