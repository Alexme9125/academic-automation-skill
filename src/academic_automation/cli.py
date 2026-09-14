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
from http.client import HTTPException
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
    s.add_argument('query', nargs='?'); s.add_argument('output'); s.add_argument('--pages', type=int, default=1)
    s.add_argument('--query-file', help='Read an exact UTF-8 query, avoiding shell quote conversion')
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
    u.add_argument('--route', choices=['auto', 'pmc-only'], default='auto')
    u.add_argument('--on-unavailable', choices=['defer', 'bibliography'], default='defer', help='PMC-only: preserve a deferred item or deliver bibliography')
    b = sub.add_parser('batch'); b.add_argument('input'); b.add_argument('--expert', default=''); b.add_argument('--affiliation', default='')
    b.add_argument('--pages', type=int, default=3); b.add_argument('--refresh-index', action='store_true'); b.add_argument('--retry', action='store_true')
    b.add_argument('--source', choices=['cnki', 'pubmed'], default='cnki'); b.add_argument('--dest')
    b.add_argument('--access-policy', choices=access.CHOICES)
    b.add_argument('--route', choices=['auto', 'pmc-only'], default='auto')
    b.add_argument('--on-unavailable', choices=['defer', 'bibliography'], default='defer')
    control = b.add_mutually_exclusive_group()
    control.add_argument('--cancel', action='store_true', help='Record the actual user request to stop this entire PubMed manifest')
    control.add_argument('--resume-cancelled', action='store_true', help='Explicitly restart a user-cancelled PubMed batch')
    b.add_argument('--note', help='Actual user reply authorizing cancellation or restart')
    b = sub.add_parser('bibliography'); b.add_argument('source', choices=['cnki', 'scholar', 'wos', 'pubmed'])
    b.add_argument('input'); b.add_argument('output'); b.add_argument('--title'); b.add_argument('--theme', default='')
    b.add_argument('--progress', help='PubMed batch checkpoint to merge with metadata')
    a = sub.add_parser('archive'); a.add_argument('dest'); a.add_argument('--file', help='Explicit manually saved PDF/CAJ')
    a.add_argument('--name', default=''); a.add_argument('--snapshot'); a.add_argument('--minutes', type=float, default=5)
    a.add_argument('--author', default='')
    a.add_argument('--checkpoint', help='Complete a pending download using an explicitly verified manual file')
    a.add_argument('--confirm-identity', action='store_true', help='Only after the user reviews a reported glyph ambiguity')
    a.add_argument('--pending-id'); a.add_argument('--sha256'); a.add_argument('--note')
    return p


def normalize_args(a):
    if a.command == 'search':
        if a.query_file:
            if a.query is not None:
                raise BrowserError('Use a positional query OR --query-file, not both', 64)
            a.query = Path(a.query_file).read_text(encoding='utf-8-sig').strip()
        if not a.query or not a.query.strip():
            raise BrowserError('QUERY_REQUIRED: provide query text or --query-file with UTF-8 contents', 64)
    if a.command == 'batch' and a.source != 'pubmed' and (a.route != 'auto' or a.on_unavailable != 'defer' or a.cancel or a.resume_cancelled or a.note):
        raise BrowserError('Route and batch control options require --source pubmed', 64)
    if getattr(a, 'on_unavailable', 'defer') != 'defer' and a.route != 'pmc-only':
        raise BrowserError('--on-unavailable requires --route pmc-only', 64)
    if a.command == 'batch' and (a.cancel or a.resume_cancelled) and not (a.note or '').strip():
        raise BrowserError('Record the actual user reply with --note before cancelling or restarting a batch', 64)


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
    if backend == 'extension':
        result['capabilities']['browser']['extension_token'] = {
            'present': browser.extension_token_present(), 'required_for_new_connection': True,
            'environment_variable': 'PLAYWRIGHT_MCP_EXTENSION_TOKEN', 'authentication_verified': False}
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
            return {'backend': browser.backend_name(), 'session': browser.session_name(), 'connection': browser.connection_status(),
                    'pending': interaction.read(),
                    'api_pending': interaction.api_pending(),
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
        if a.source == 'pubmed': return pubmed.download(a.pmid, a.dest, a.name, a.retry, a.route, a.on_unavailable)
        if a.source == 'cnki':
            return cnki.download(a.title, a.author, a.dest, a.expert, a.affiliation, a.pages, a.index, a.retry)
        return publisher.download(a.doi, a.dest, a.name, a.retry)
    if a.command == 'batch':
        if a.source == 'pubmed':
            lock = 'pubmed-batch-' + hashlib.sha256(str(Path(a.input).resolve()).encode()).hexdigest()[:20]
            with browser.browser_lock(lock): return pubmed.batch(a)
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
        if a.source == 'pubmed': return pubmed.bibliography(a.input, a.output, a.title, a.progress)
        if a.progress: raise BrowserError('--progress requires PubMed bibliography', 64)
        args = [a.input, a.output, '--theme', a.theme]
        if a.title: args += ['--title', a.title]
        invoke({'scholar': 'gs_bib', 'cnki': 'cnki_bib', 'wos': 'wos_bib'}[a.source], args)
        return {'output': str(Path(a.output).resolve())}
    if a.command == 'archive':
        if a.confirm_identity and not a.checkpoint:
            raise BrowserError('--confirm-identity requires a matching --checkpoint and --file', 64)
        if a.checkpoint:
            state = br.read_json(a.checkpoint)
            recoverable = isinstance(state, dict) and (state.get('status') in ('waiting', 'archiving')
                or state.get('status') == 'complete' and (state.get('verification', {}).get('status') == 'invalid'
                    or a.confirm_identity and state.get('manual_identity')))
            if not a.file or not recoverable:
                raise BrowserError('--checkpoint requires --file and a pending download checkpoint', 64)
            if Path(a.checkpoint).resolve().parent != Path(a.dest).resolve() / '.academic-downloads':
                raise BrowserError('Checkpoint belongs to a different destination', 64)
            if a.confirm_identity:
                from .manual_identity import archive
                return archive(a, state)
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
        normalize_args(a)
        for key, env in [('backend', 'ACADEMIC_BROWSER_BACKEND'), ('session', 'ACADEMIC_BROWSER_SESSION'), ('downloads_dir', 'CNKI_DOWNLOADS_DIR')]:
            if getattr(a, key): os.environ[env] = getattr(a, key)
        # Validate identity before any browser or lock activity.
        if a.command == 'download' and a.source == 'cnki' and (not a.author.strip() or not a.title.strip()):
            raise BrowserError('NEED_AUTHOR: Chinese downloads require title and first author', 64)
        needs_lock = a.command in ('search', 'metadata', 'download') or (a.command == 'browser' and a.action != 'status') or (a.command == 'archive' and a.checkpoint)
        # Batch child processes acquire their own lock; there is no interactive stdin.
        with contextlib.redirect_stdout(sys.stderr):
            if a.command == 'batch' and a.source == 'pubmed':
                a.resume_argv = [sys.executable, str(ROOT / 'scripts/academic.py'), *argv]
            api_lock = interaction.api_only(a)
            if a.command == 'archive' and a.checkpoint:
                api_lock = any(p.get('checkpoint') and Path(p['checkpoint']).resolve() == Path(a.checkpoint).resolve()
                               for p in interaction.api_pending())
            if a.command == 'browser' and a.action == 'resolve':
                api_lock = (interaction.pending_for_id(a.pending_id) or {}).get('channel') == 'pubmed-data'
            with browser.browser_lock('pubmed-data' if api_lock else 'browser') if needs_lock else contextlib.nullcontext():
                if a.command in ('search', 'metadata', 'download') or (a.command == 'archive' and a.checkpoint):
                    result = interaction.execute(a, [sys.executable, str(ROOT / 'scripts/academic.py'), *argv], lambda: dispatch(a))
                else:
                    result = dispatch(a)
    except BrowserError as exc:
        code = exc.code; result = {'message': str(exc), **exc.details}
        if code == 2 and 'pending' not in result and interaction.read() and not interaction.api_only(a):
            result.update(interaction.details())
        elif code == 70 and interaction.read() and not interaction.api_only(a):
            result.update(pending=interaction.read(), may_continue_browser=False)
    except HTTPException:
        code = 70; result = {'message': 'HTTP_TRANSFER_ERROR: retry the original task; inspect its checkpoint first', 'retryable': True}
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
