"""Argument compatibility for the original macOS shell commands."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

from . import cli, cnki
from .browser import browser_lock
from .browser_runtime import run_js, navigate
from .errors import BrowserError


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    mode, args = args[0], args[1:]
    try:
        if mode == 'foreign':
            p = cli.Parser(); p.add_argument('query'); p.add_argument('--rows', action='store_true')
            a = p.parse_args(args)
            with browser_lock(), tempfile.TemporaryDirectory(prefix='academic-foreign-') as tmp:
                result = cnki.foreign_search(a.query, Path(tmp) / 'rows.json')
            print('QUERY: ' + a.query)
            print('RESULT: OK n=' + str(result.get('total', result['n'])))
            if a.rows: print('ROWS: ' + json.dumps(result, ensure_ascii=False))
            return 0
        if mode == 'oa':
            p = cli.Parser(); p.add_argument('doi'); p.add_argument('dest'); p.add_argument('name', nargs='?', default='')
            a = p.parse_args(args)
            code = cli.main(['download', 'doi', a.doi, a.dest, '--name', a.name])
            return 3 if code == 2 else code
        if mode == 'archive':
            p = cli.Parser(); p.add_argument('dest'); p.add_argument('name', nargs='?', default='')
            p.add_argument('minutes', nargs='?', default='5'); p.add_argument('--snapshot')
            a = p.parse_args(args)
            name = a.name if not a.name or a.name.lower().endswith('.pdf') else a.name + '.pdf'
            call = ['archive', a.dest, '--name', name, '--minutes', a.minutes]
            if a.snapshot: call += ['--snapshot', a.snapshot]
            return cli.main(call)
        if mode in ('navigate', 'javascript'):
            if len(args) != 1: raise BrowserError('Expected one URL or JavaScript file', 64)
            with browser_lock():
                result = navigate(args[0]) if mode == 'navigate' else run_js(Path(args[0]).read_text(encoding='utf-8'))
            if result is not None: print(result)
            return 0
        raise BrowserError('Unknown legacy command', 64)
    except BrowserError as exc:
        print(str(exc))
        return exc.code
