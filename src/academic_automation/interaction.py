"""Persist a human handoff across commands, processes and installed skill copies.

This is a workflow guard, not proof that a model actually obtained a human reply.
Harnesses must enforce that provenance before invoking resolve().
"""
import hashlib
import json
import time
import uuid
from contextvars import ContextVar
from contextlib import contextmanager
from pathlib import Path

from .errors import BrowserError
from .paths import state_dir

_task = ContextVar('academic_task', default=None)
_pending_key = ContextVar('academic_pending_key', default=None)


def api_only(args):
    return args.command in ('search', 'metadata') and getattr(args, 'source', '') == 'pubmed'


@contextmanager
def pending_scope(key):
    token = _pending_key.set(key)
    try: yield
    finally: _pending_key.reset(token)


def require_task():
    if _task.get() is None:
        raise BrowserError('USE_UNIFIED_CLI: run scripts/academic.py; direct workflow calls omit locking and human handoffs', 64)


@contextmanager
def _scope(key):
    token = _task.set(key)
    try:
        yield
    finally:
        _task.reset(token)


def path():
    if _pending_key.get(): return state_dir() / 'api-pending' / (_pending_key.get() + '.json')
    return state_dir() / 'pending-user.json'


def api_pending():
    from .browser_runtime import read_json
    return [read_json(p) for p in sorted((state_dir() / 'api-pending').glob('*.json'))]


def pending_for_id(ident):
    pending = read()
    if pending and pending['id'] == ident: return pending
    return next((p for p in api_pending() if p and p.get('id') == ident), None)


def read():
    if not path().exists():
        return None
    data = json.loads(path().read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not data.get('id') or not data.get('action'):
        raise BrowserError('INVALID_PENDING_STATE: inspect pending-user.json', 74)
    return data


def write(data):
    from .browser_runtime import atomic_json
    atomic_json(path(), data)


def clear():
    path().unlink(missing_ok=True)


def action(args):
    from .browser import backend_name, session_name
    values = {k: v for k, v in vars(args).items() if k not in
              ('json', 'backend', 'session', 'downloads_dir', 'retry', 'refresh', 'refresh_index', 'access_policy')}
    # New optional interface fields must not invalidate existing Beta 3 handoffs.
    for key, default in (('free_full_text', False), ('sort', 'relevance'), ('progress', None),
                         ('confirm_identity', False), ('pending_id', None), ('sha256', None), ('note', None)):
        if values.get(key) == default: values.pop(key, None)
    if args.command in ('metadata', 'batch') and values.get('source') == 'cnki':
        values.pop('source', None)
    if args.command == 'batch' and values.get('dest') is None: values.pop('dest', None)
    if args.command == 'doctor': values.pop('capability', None)
    for key in ('input', 'output', 'dest', 'file', 'checkpoint', 'meta_script', 'index'):
        if values.get(key):
            values[key] = str(Path(values[key]).resolve())
    if api_only(args):
        values.pop('meta_script', None)
        values['transport'] = 'pubmed-data'
    else: values.update(backend=backend_name(), session=session_name())
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def details(pending=None):
    pending = pending or read()
    kind = pending.get('details', {}).get('kind')
    if kind in ('access_unknown', 'identity_review'):
        message = ('Keep this article pending. Ask the user to inspect article-level free-access evidence, '
                   'or choose bibliography, skip or replacement. Missing free evidence is not a subscription finding.'
                   if kind == 'access_unknown' else
                   'Review the saved PDF title, authors and DOI with the user. After an actual confirmation use '
                   'archive --confirm-identity with this pending id, candidate SHA-256 and --note containing the reply. '
                   'Do not use skip or disable verification to mark it archived.')
        return {'pending': pending, 'wait_for_user': True, 'may_continue_browser': False, 'next_action': message}
    if pending.get('details', {}).get('kind') == 'access_policy':
        return {'pending': pending, 'wait_for_user': True, 'may_continue_browser': False,
                'next_action': 'Ask whether to include subscription articles. If declined, ask whether to exclude them or keep bibliography. '
                               'WAIT for the actual reply, then browser resolve --decision retry --access-policy <choice> --note <reply>.'}
    if 'NEED_CONNECTION' in pending.get('message', ''):
        return {'pending': pending, 'wait_for_user': True, 'may_continue_browser': False,
                'next_action': 'Wait for the actual user reply. Then browser resolve --decision retry, '
                               'browser connect to bind the current article tab, then repeat resume_argv. '
                               'Retry alone does not repair a stale tab binding.'}
    return {'pending': pending, 'wait_for_user': True, 'may_continue_browser': False,
            'next_action': 'Ask the user to handle the current page and WAIT for their reply. '
                           'Do not mark this article unavailable or navigate to another article. '
                           'After a reply, use browser resolve with the pending id; '
                           'already saved files can be recovered by repeating the original command.'}


def blocked(pending):
    raise BrowserError('WAITING_FOR_USER: ' + pending['message'], 2, details(pending))


def resolve(pending_id, decision, note, access_policy=None, pmc_version=None):
    from .browser_runtime import read_json
    pending = pending_for_id(pending_id)
    if not pending and pending_id and len(pending_id) == 32 and all(c in '0123456789abcdef' for c in pending_id):
        pending = read_json(state_dir() / 'user-decisions' / (pending_id + '.json'), {})
    key = pending['action'] if pending and pending.get('channel') == 'pubmed-data' else None
    with pending_scope(key): return _resolve(pending_id, decision, note, access_policy, pmc_version)


def _resolve(pending_id, decision, note, access_policy=None, pmc_version=None):
    pending = read()
    if not pending and pending_id and all(c in '0123456789abcdef' for c in pending_id) and len(pending_id) == 32:
        saved = state_dir() / 'user-decisions' / (pending_id + '.json')
        if saved.is_file() and decision == 'retry':
            pending = json.loads(saved.read_text(encoding='utf-8'))
    if not pending or pending['id'] != pending_id:
        raise BrowserError('PENDING_ID_MISMATCH: run browser status', 64)
    if decision not in ('retry', 'skip') or not note or not note.strip():
        raise BrowserError('Record the actual user reply with --decision retry|skip and --note', 64)
    if decision == 'retry' and pending.get('details', {}).get('kind') == 'access_policy':
        from . import access
        access.save(pending['action'], access_policy)
        pending['access_policy'] = access_policy
    if decision == 'retry' and pending.get('details', {}).get('kind') == 'pmc_version':
        from .browser_runtime import read_json, atomic_json
        versions = pending['details'].get('versions', [])
        if pmc_version not in [x.get('version') for x in versions]:
            raise BrowserError('Select a listed --pmc-version after an actual user reply', 64)
        checkpoint = pending['checkpoint']; state = read_json(checkpoint)
        state['selected_pmc_version'] = pmc_version
        atomic_json(checkpoint, state)
    pending['user_decision'] = {'decision': decision, 'note': note.strip(), 'time': time.time()}
    if decision == 'skip':
        # Keep evidence that this was an explicit user choice, not a paywall claim.
        from .browser_runtime import atomic_json
        atomic_json(state_dir() / 'user-decisions' / (pending['id'] + '.json'), pending)
        atomic_json(state_dir() / 'skipped-actions' / (pending['action'] + '.json'), pending)
        clear()
        return {'status': 'skipped_by_user', 'pending_id': pending_id}
    pending['user_confirmed'] = True
    (state_dir() / 'skipped-actions' / (pending['action'] + '.json')).unlink(missing_ok=True)
    write(pending)
    return {'status': 'ready_to_retry_original', 'pending_id': pending_id,
            'resume_argv': pending['resume_argv']}


def run(key, argv, callback, recover=None):
    """Caller holds browser_lock. Only the paused action may proceed after a reply."""
    pending = read()
    skipped = state_dir() / 'skipped-actions' / (key + '.json')
    if not pending and skipped.is_file():
        decision = json.loads(skipped.read_text(encoding='utf-8'))
        raise BrowserError('SKIPPED_BY_USER: this article was explicitly skipped', 6,
                           {'pending_id': decision['id'], 'user_decision': decision['user_decision']})
    if pending:
        if key != pending['action']:
            blocked(pending)
        # File recovery precedes any navigation or user-ack requirement.
        if recover:
            recovered = recover(pending)
            if recovered:
                clear()
                return recovered
        if not pending.get('user_confirmed'):
            blocked(pending)
    try:
        with _scope(key):
            result = callback(bool(pending and pending.get('user_confirmed')))
    except BrowserError as exc:
        if exc.code != 2:
            # A definitive result after an acknowledged retry ends this handoff.
            # Transient/protocol failures keep the pending task protected.
            if pending and exc.code in (1, 3, 5) and not exc.details.get('retryable'):
                clear()
            raise
        state = {'id': pending['id'] if pending else uuid.uuid4().hex,
                 'action': key, 'resume_argv': list(argv), 'message': str(exc),
                 'checkpoint': exc.details.get('checkpoint', ''),
                 'details': exc.details, 'user_confirmed': False, 'time': time.time()}
        if _pending_key.get(): state['channel'] = 'pubmed-data'
        from . import access
        policy = exc.details.get('access_policy') or access.current() or (pending or {}).get('access_policy')
        if policy: state['access_policy'] = policy
        write(state)
        raise BrowserError(str(exc), 2, {**exc.details, **details(state)}) from exc
    if pending:
        clear()
    return result


def execute(args, argv, callback):
    if api_only(args):
        key = action(args)
        # Preserve an API handoff created by Beta 4's global pending mechanism.
        old = read()
        if old and not old.get('channel'):
            from .cli import parser
            try:
                previous = parser().parse_args(old['resume_argv'][2:])
                migrate = api_only(previous) and action(previous) == key
            except (KeyError, BrowserError): migrate = False
            if migrate:
                with pending_scope(key):
                    old.update(action=key, channel='pubmed-data'); write(old)
                    if old.get('user_confirmed') and old.get('access_policy'):
                        from . import access
                        access.save(key, old['access_policy'])
                clear()
        with pending_scope(key): return _execute(args, argv, callback)
    return _execute(args, argv, callback)


def _execute(args, argv, callback):
    from . import access
    key = action(args)
    def recover(pending):
        checkpoint = pending.get('checkpoint')
        if args.command != 'download' or not checkpoint:
            return None
        from .cnki import resume_download
        from .browser_runtime import read_json
        try:
            return resume_download(checkpoint, args.dest, getattr(args, 'author', ''),
                                   name=read_json(checkpoint, {}).get('name', getattr(args, 'name', '')))
        except BrowserError as exc:
            if exc.code != 2:
                raise
        return None

    pending = read()
    if (pending and pending['action'] == key and pending.get('access_policy')
            and getattr(args, 'access_policy', None) not in (None, pending['access_policy'])):
        blocked(pending)
    if args.command == 'archive' and args.checkpoint and pending:
        if Path(args.checkpoint).resolve() != Path(pending.get('checkpoint') or '.').resolve():
            blocked(pending)
        result = callback()
        clear()
        return result

    def perform(confirmed):
        if confirmed and args.command == 'download':
            args.retry = True
        policy = access.prepare(args, key)
        with access.scope(policy):
            try:
                return callback()
            except BrowserError as exc:
                if policy: exc.details['access_policy'] = policy
                raise
    return run(key, argv, perform, recover)
