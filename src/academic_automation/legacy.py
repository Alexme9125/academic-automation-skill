"""Argument compatibility for the original macOS shell commands."""
import argparse
import json
import sys
import contextlib
import io
import hashlib
from pathlib import Path

from . import cli, interaction
from .paths import state_dir
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
            output = state_dir() / ('legacy-foreign-' + hashlib.sha256(a.query.encode()).hexdigest()[:16] + '.json')
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                code = cli.main(['--json', 'search', 'cnki-foreign', a.query, str(output), '--refresh'])
            response = json.loads(capture.getvalue())
            if code:
                print(json.dumps(response, ensure_ascii=False))
                return code
            result = response['result']
            print('QUERY: ' + a.query)
            print('RESULT: OK n=' + str(result.get('total', result['n'])))
            if a.rows: print('ROWS: ' + json.dumps(result, ensure_ascii=False))
            return 0
        if mode == 'oa':
            p = cli.Parser(); p.add_argument('doi'); p.add_argument('dest'); p.add_argument('name', nargs='?', default='')
            a = p.parse_args(args)
            code = cli.main(['download', 'doi', a.doi, a.dest, '--name', a.name])
            return code
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
                result = interaction.run('legacy-' + mode + ':' + args[0],
                    [sys.executable, sys.argv[0], mode, *args],
                    lambda confirmed: navigate(args[0]) if mode == 'navigate' else run_js(Path(args[0]).read_text(encoding='utf-8')))
            if result is not None: print(result)
            return 0
        raise BrowserError('Unknown legacy command', 64)
    except BrowserError as exc:
        print(str(exc))
        if exc.code == 2 and interaction.read():
            print(json.dumps(interaction.details(), ensure_ascii=False))
        return exc.code
