"""Stable command interface for local agents; stdout can be one JSON object."""
import argparse
import contextlib
import importlib
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
import subprocess
from pathlib import Path

from . import browser, browser_runtime as br, cnki, publisher, download_watch as dw, interaction, access, pubmed, pdf_verify
from .errors import BrowserError
from .paths import ROOT, downloads_dir


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise BrowserError(message, 64)


def version():
    return re.search(r'version:\s*"([^"]+)"', (ROOT / 'SKILL.md').read_text(encoding='utf-8')).group(1)


def invoke(module, arguments):
    old = sys.argv
    try:
        sys.argv = [module] + [str(arg) for arg in arguments]
        importlib.import_module('.' + module, __package__).main()
    except SystemExit as exc:
        if exc.code:
            raise BrowserError(module + ' did not complete', int(exc.code)) from exc
    finally:
        sys.argv = old


def parser():
    p = Parser(description='Academic search, downloads and bibliography for local agents')
    p.add_argument('--version', action='version', version=version())
    p.add_argument('--json', action='store_true', help='One structured result on stdout; diagnostics on stderr')
    p.add_argument('--backend', choices=['apple-events', 'extension'])
    p.add_argument('--session', help='Browser connection name; default: academic')
    p.add_argument('--downloads-dir', help='Chrome actual download directory')
    sub = p.add_subparsers(dest='command', required=True, parser_class=Parser)
    d = sub.add_parser('doctor'); d.add_argument('--browser', action='store_true', help='Also test the connected tab')
    d.add_argument('--capability', choices=['browser', 'pubmed-data'], default='browser')
    b = sub.add_parser('browser'); b.add_argument('action', choices=['connect', 'disconnect', 'status', 'resolve'])
    b.add_argument('--url', default='', help='Create a new explicit task tab when connecting the extension')
    b.add_argument('--pending-id'); b.add_argument('--decision', choices=['retry', 'skip']); b.add_argument('--note')
    b.add_argument('--access-policy', choices=access.CHOICES)
    b.add_argument('--pmc-version', type=int, help='Only after a human selects one of the pending PMC versions')
    s = sub.add_parser('search'); s.add_argument('source', choices=['cnki', 'cnki-foreign', 'scholar', 'wos', 'pubmed'])
    s.add_argument('query'); s.add_argument('output'); s.add_argument('--pages', type=int, default=1)
    s.add_argument('--year', default=''); s.add_argument('--oa', action='store_true'); s.add_argument('--refresh', action='store_true')
    s.add_argument('--expert', action='store_true', help='CNKI Chinese: query is an exact expert expression')
    s.add_argument('--access-policy', choices=access.CHOICES)
    s.add_argument('--sort', choices=['relevance', 'pub_date'], default='relevance')
    s.add_argument('--free-full-text', action='store_true')
    m = sub.add_parser('metadata'); m.add_argument('input'); m.add_argument('output')
    m.add_argument('--refresh', action='store_true'); m.add_argument('--meta-script', default=str(br.DIR / 'cnki_meta.js'))
    m.add_argument('--source', choices=['cnki', 'pubmed'], default='cnki')
    m.add_argument('--access-policy', choices=access.CHOICES)
    d = sub.add_parser('download'); modes = d.add_subparsers(dest='source', required=True, parser_class=Parser)
    c = modes.add_parser('cnki'); c.add_argument('title'); c.add_argument('author'); c.add_argument('dest')
    c.add_argument('--expert', default=''); c.add_argument('--affiliation', default='')
    c.add_argument('--pages', type=int, default=3); c.add_argument('--index', default=''); c.add_argument('--retry', action='store_true')
    o = modes.add_parser('doi'); o.add_argument('doi'); o.add_argument('dest'); o.add_argument('--name', default=''); o.add_argument('--retry', action='store_true')
    o.add_argument('--access-policy', choices=access.CHOICES)
    u = modes.add_parser('pubmed'); u.add_argument('pmid'); u.add_argument('dest'); u.add_argument('--name', default=''); u.add_argument('--retry', action='store_true')
    u.add_argument('--access-policy', choices=access.CHOICES)
    b = sub.add_parser('batch'); b.add_argument('input'); b.add_argument('--expert', default=''); b.add_argument('--affiliation', default='')
    b.add_argument('--pages', type=int, default=3); b.add_argument('--refresh-index', action='store_true'); b.add_argument('--retry', action='store_true')
    b.add_argument('--source', choices=['cnki', 'pubmed'], default='cnki'); b.add_argument('--dest')
    b.add_argument('--access-policy', choices=access.CHOICES)
    b = sub.add_parser('bibliography'); b.add_argument('source', choices=['cnki', 'scholar', 'wos', 'pubmed'])
    b.add_argument('input'); b.add_argument('output'); b.add_argument('--title'); b.add_argument('--theme', default='')
    a = sub.add_parser('archive'); a.add_argument('dest'); a.add_argument('--file', help='Explicit manually saved PDF/CAJ')
    a.add_argument('--name', default=''); a.add_argument('--snapshot'); a.add_argument('--minutes', type=float, default=5)
    a.add_argument('--author', default='')
    a.add_argument('--checkpoint', help='Complete a pending download using an explicitly verified manual file')
    return p


def doctor(probe=False):
    expected = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['dependencies']['@playwright/cli']
    manifest = ROOT / 'node_modules' / '@playwright' / 'cli' / 'package.json'
    installed = json.loads(manifest.read_text(encoding='utf-8')).get('version') if manifest.is_file() else None
    backend = browser.backend_name()
    node = shutil.which('node')
    node_version = subprocess.run([node, '--version'], capture_output=True, text=True, timeout=10).stdout.strip() if node else ''
    node_ready = bool(re.match(r'^v(\d+)\.', node_version) and int(re.match(r'^v(\d+)\.', node_version).group(1)) >= 22)
    ready = bool(shutil.which('osascript')) if backend == 'apple-events' else bool(node_ready and installed == expected)
    fingerprint = hashlib.sha256()
    sources = [ROOT / 'SKILL.md', ROOT / 'package-lock.json']
    for folder in ('src', 'scripts', 'references'):
        sources.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and p.suffix in ('.py', '.js', '.sh', '.md'))
    for source in sorted(sources):
        fingerprint.update(source.relative_to(ROOT).as_posix().encode() + b'\0' + source.read_bytes() + b'\0')
    result = {'version': version(), 'platform': platform.system(), 'python': platform.python_version(),
              'code_fingerprint': fingerprint.hexdigest(),
              'backend': backend, 'runtime_ready': ready, 'browser_verified': False,
              'node': node, 'node_version': node_version, 'playwright_cli_expected': expected, 'playwright_cli_installed': installed,
              'downloads': str(downloads_dir()), 'downloads_exists': downloads_dir().is_dir(),
              'windows_validation': 'pending tester acceptance'}
    result['capabilities'] = {'pubmed_data': {'runtime_ready': True, 'network_verified': False, 'requires_browser': False},
                              'browser': {'runtime_ready': ready, 'verified': False},
                              'pdf_identity': {'available': pdf_verify.available(), 'optional': True,
                                               'install': pdf_verify.INSTALL, 'note': pdf_verify.WARNING}}
    if probe:
        with browser.browser_lock():
            transport = browser.get_browser()
            if backend == 'extension' and not browser.read_session().get('connected'):
                raise BrowserError('NEED_CONNECTION: connect the extension before verifying its task tab', 2)
            result['page'] = transport.probe() if backend == 'extension' else json.loads(br.run_js('JSON.stringify({title:document.title,url:location.href})'))
        result['browser_verified'] = True
        result['capabilities']['browser'].update(verified=True, download_verified=False)
    return result


def dispatch(a):
    if a.command == 'doctor':
        result = doctor(a.browser)
        if not result['runtime_ready'] and a.capability != 'pubmed-data':
            raise BrowserError('MISSING_RUNTIME: see runtime checks', 69, result)
        return result
    if a.command == 'browser':
        if a.action == 'resolve':
            return interaction.resolve(a.pending_id, a.decision, a.note, a.access_policy, a.pmc_version)
        if a.action == 'status':
            return {'backend': browser.backend_name(), 'session': browser.session_name(), 'connection': browser.read_session(),
                    'pending': interaction.read(),
                    'note': 'Saved connection metadata; use doctor --browser for a live check'}
        if a.action == 'connect' and interaction.read() and not interaction.read().get('user_confirmed'):
            interaction.blocked(interaction.read())
        transport = browser.get_browser()
        if a.action == 'connect' and a.url:
            if browser.backend_name() != 'extension': raise BrowserError('--url is only supported by extension connect', 64)
            return transport.connect(a.url)
        return getattr(transport, a.action)()
    if a.command == 'search':
        if a.source != 'pubmed' and (a.free_full_text or a.sort != 'relevance'):
            raise BrowserError('--free-full-text and --sort are PubMed options', 64)
        if a.oa and a.source != 'wos':
            raise BrowserError('--oa is supported only for WoS', 64)
        if a.year and a.source != 'scholar':
            raise BrowserError('--year is supported only for Scholar', 64)
        if a.expert and a.source != 'cnki':
            raise BrowserError('--expert is supported only for Chinese CNKI search', 64)
        if a.source == 'pubmed':
            return pubmed.search(a.query, a.output, a.pages, a.sort, a.free_full_text, a.refresh)
        if a.source == 'cnki':
            return cnki.chinese_search(a.query, a.output, a.pages, a.refresh, a.expert)
        if a.source == 'cnki-foreign':
            return cnki.foreign_search(a.query, a.output, a.pages, a.refresh)
        from . import search_resume as sr
        a.mode = a.source; sr.search(a)
        return {'output': str(Path(a.output).resolve()), **br.read_json(a.output, {})}
    if a.command == 'metadata':
        if a.source == 'pubmed': return pubmed.metadata(a.input, a.output, a.refresh)
        from . import search_resume as sr
        a.query = a.input; sr.metadata(a)
        return {'output': str(Path(a.output).resolve()), 'records': len(br.read_json(a.output, []))}
    if a.command == 'download':
        if a.source == 'pubmed': return pubmed.download(a.pmid, a.dest, a.name, a.retry)
        if a.source == 'cnki':
            return cnki.download(a.title, a.author, a.dest, a.expert, a.affiliation, a.pages, a.index, a.retry)
        return publisher.download(a.doi, a.dest, a.name, a.retry)
    if a.command == 'batch':
        if a.source == 'pubmed': return pubmed.batch(a)
        args = [a.input, '--pages', a.pages]
        for key in ('expert', 'affiliation'):
            if getattr(a, key): args += ['--' + key, getattr(a, key)]
        for key in ('refresh_index', 'retry'):
            if getattr(a, key): args += ['--' + key.replace('_', '-')]
        invoke('cnki_batch', args)
        from .cnki_batch import state_path
        checkpoint = Path(a.input).with_suffix('.progress.json').resolve()
        return {'state': str(Path(state_path(a.input)).resolve()), 'checkpoint': str(checkpoint),
                **br.read_json(checkpoint, {}).get('summary', {})}
    if a.command == 'bibliography':
        if a.source == 'pubmed': return pubmed.bibliography(a.input, a.output, a.title)
        args = [a.input, a.output, '--theme', a.theme]
        if a.title: args += ['--title', a.title]
        invoke({'scholar': 'gs_bib', 'cnki': 'cnki_bib', 'wos': 'wos_bib'}[a.source], args)
        return {'output': str(Path(a.output).resolve())}
    if a.command == 'archive':
        if a.checkpoint:
            state = br.read_json(a.checkpoint)
            recoverable = isinstance(state, dict) and (state.get('status') in ('waiting', 'archiving')
                or state.get('status') == 'complete' and state.get('verification', {}).get('status') == 'invalid')
            if not a.file or not recoverable:
                raise BrowserError('--checkpoint requires --file and a pending download checkpoint', 64)
            if Path(a.checkpoint).resolve().parent != Path(a.dest).resolve() / '.academic-downloads':
                raise BrowserError('Checkpoint belongs to a different destination', 64)
            return cnki.finish_download(a.file, a.dest, a.checkpoint, state, a.name or state.get('name', ''))
        before = br.read_json(a.snapshot) if a.snapshot else None
        if a.snapshot and before is None:
            raise BrowserError('Missing or invalid download snapshot', 64)
        path = Path(a.file) if a.file else dw.wait_download(downloads_dir(), before, a.author,
                                                         time.time() - a.minutes * 60, timeout=30)
        verification = pdf_verify.verify(path, {}) if path.suffix.lower() == '.pdf' else {'content_verified': False, 'reason': 'caj_format'}
        return {'path': str(dw.archive(path, a.dest, a.name)), 'verification': verification}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = '--json' in argv
    code, result = 0, {}
    try:
        a = parser().parse_args(argv)
        for key, env in [('backend', 'ACADEMIC_BROWSER_BACKEND'), ('session', 'ACADEMIC_BROWSER_SESSION'), ('downloads_dir', 'CNKI_DOWNLOADS_DIR')]:
            if getattr(a, key): os.environ[env] = getattr(a, key)
        # Validate identity before any browser or lock activity.
        if a.command == 'download' and a.source == 'cnki' and (not a.author.strip() or not a.title.strip()):
            raise BrowserError('NEED_AUTHOR: Chinese downloads require title and first author', 64)
        needs_lock = a.command in ('search', 'metadata', 'download') or (a.command == 'browser' and a.action != 'status') or (a.command == 'archive' and a.checkpoint)
        # Batch child processes acquire their own lock; there is no interactive stdin.
        with contextlib.redirect_stdout(sys.stderr):
            if a.command == 'batch' and a.source == 'pubmed':
                # A paused child must be resumed by that same child, not blocked by
                # its parent manifest's identity. Only missing-scope handoffs live here.
                with browser.browser_lock():
                    pending = interaction.read()
                    if not pending or pending['action'] == interaction.action(a):
                        interaction.execute(a, [sys.executable, str(ROOT / 'scripts/academic.py'), *argv], lambda: {})
                    else:
                        access.prepare(a, interaction.action(a))
            with browser.browser_lock() if needs_lock else contextlib.nullcontext():
                if a.command in ('search', 'metadata', 'download') or (a.command == 'archive' and a.checkpoint):
                    result = interaction.execute(a, [sys.executable, str(ROOT / 'scripts/academic.py'), *argv], lambda: dispatch(a))
                else:
                    result = dispatch(a)
    except BrowserError as exc:
        code = exc.code; result = {'message': str(exc), **exc.details}
        if code == 2 and interaction.read():
            result.update(interaction.details())
        elif code == 70 and interaction.read():
            result.update(pending=interaction.read(), may_continue_browser=False)
    except (OSError, ValueError) as exc:
        code = 74; result = {'message': str(exc)}
    except KeyboardInterrupt:
        code = 130; result = {'message': 'Interrupted; repeat the command to resume saved progress'}
    status = 'complete' if code == 0 else 'needs_user' if code == 2 else 'skipped' if code == 6 else 'busy' if code == 75 else 'failed'
    from .redaction import redact
    result = redact(result)
    response = {'ok': code == 0, 'status': status, 'code': code, 'result': result}
    if as_json:
        print(json.dumps(response, ensure_ascii=False))
    elif code:
        print(result.get('message', str(result)))
    elif result.get('path'):
        print('ARCHIVED: ' + result['path'])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return code
