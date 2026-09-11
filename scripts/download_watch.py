#!/usr/bin/env python3
"""Watch only completed candidates belonging to this download, then archive safely."""
import argparse
import os
import re
import shutil
import sys
import time
from pathlib import Path
from browser_runtime import atomic_json, read_json, run_file, BrowserError


def snapshot(folder):
    found = {}
    for p in Path(folder).iterdir():
        try:
            if p.is_file():
                s = p.stat()
                found[p.name] = [s.st_size, s.st_mtime_ns]
        except OSError:
            pass
    return found


def valid_file(path):
    p = Path(path)
    try:
        if p.stat().st_size == 0:
            return False
        with p.open('rb') as f:
            head = f.read(8)
        return head.startswith(b'%PDF-') if p.suffix.lower() == '.pdf' else p.suffix.lower() == '.caj'
    except OSError:
        return False


def candidates(folder, before, author='', since=0):
    result = []
    for name, sig in snapshot(folder).items():
        p = Path(folder) / name
        if name.startswith('._') or p.suffix.lower() not in ('.pdf', '.caj'):
            continue
        if author and not re.search('_' + re.escape(author) + r'(?: \(\d+\))?\.(?:pdf|caj)$', name, re.I):
            continue
        if not author and p.suffix.lower() != '.pdf':
            continue
        if before is not None and before.get(name) == sig:
            continue
        if sig[1] / 1e9 + 2 < since or not valid_file(p):
            continue
        # Only a partial file for this candidate blocks it, never unrelated downloads.
        if p.with_name(name + '.crdownload').exists():
            continue
        result.append((p, sig))
    return result


def wait_download(folder, before=None, author='', since=0, timeout=40, page=False, interval=1):
    deadline = time.monotonic() + timeout
    previous = {}
    next_page = 0
    while time.monotonic() < deadline:
        now = time.monotonic()
        if page and now >= next_page:
            state = run_file('cnki_page.js')
            if state.startswith('captcha'):
                raise BrowserError('CAPTCHA: complete verification in Chrome', 2)
            if state.startswith('fee'):
                raise BrowserError('FEE: institution has no download access', 5)
            next_page = now + 2
        hits = candidates(folder, before, author, since)
        # Multiple new PDFs need a filename/author constraint, not a newest-file guess.
        if len(hits) == 1:
            p, sig = hits[0]
            if previous.get(str(p)) == sig:
                return p
        previous = {str(p): sig for p, sig in hits}
        time.sleep(interval)
    raise BrowserError('NOTFOUND: no unique, stable completed download', 4)


def archive(src, folder, name=''):
    src, folder = Path(src), Path(folder)
    if not valid_file(src):
        raise BrowserError('INVALID_DOWNLOAD', 4)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (Path(name).name if name else src.name)
    stem, suffix = dest.stem, dest.suffix
    n = 1
    while dest.exists():
        if src.resolve() == dest.resolve():
            return dest
        dest = folder / f'{stem} ({n}){suffix}'
        n += 1
    shutil.move(str(src), str(dest))
    if not valid_file(dest):
        raise BrowserError('ARCHIVE_INVALID', 4)
    return dest.resolve()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('snapshot'); p.add_argument('folder'); p.add_argument('output')
    p = sub.add_parser('wait'); p.add_argument('folder'); p.add_argument('--snapshot'); p.add_argument('--author', default='')
    p.add_argument('--since', type=float, default=0); p.add_argument('--timeout', type=float, default=40); p.add_argument('--page', action='store_true')
    p = sub.add_parser('archive'); p.add_argument('src'); p.add_argument('folder'); p.add_argument('--name', default='')
    args = ap.parse_args()
    try:
        if args.cmd == 'snapshot': atomic_json(args.output, snapshot(args.folder))
        elif args.cmd == 'wait':
            before = read_json(args.snapshot) if args.snapshot else None
            if args.snapshot and before is None: raise BrowserError('Missing download snapshot', 64)
            print(wait_download(args.folder, before, args.author, args.since, args.timeout, args.page))
        else: print(archive(args.src, args.folder, args.name))
    except BrowserError as e:
        print(str(e), file=sys.stderr); sys.exit(e.code)


if __name__ == '__main__':
    main()
