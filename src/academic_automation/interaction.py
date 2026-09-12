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
    return state_dir() / 'pending-user.json'


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
              ('json', 'backend', 'session', 'downloads_dir', 'retry', 'refresh', 'refresh_index')}
    for key in ('input', 'output', 'dest', 'file', 'checkpoint', 'meta_script', 'index'):
        if values.get(key):
            values[key] = str(Path(values[key]).resolve())
    values.update(backend=backend_name(), session=session_name())
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def details(pending=None):
    pending = pending or read()
    return {'pending': pending, 'wait_for_user': True, 'may_continue_browser': False,
            'next_action': 'Ask the user to handle the current page and WAIT for their reply. '
                           'Do not mark this article unavailable or navigate to another article. '
                           'After a reply, use browser resolve with the pending id; '
                           'already saved files can be recovered by repeating the original command.'}


def blocked(pending):
    raise BrowserError('WAITING_FOR_USER: ' + pending['message'], 2, details(pending))


def resolve(pending_id, decision, note):
    pending = read()
    if not pending and pending_id and all(c in '0123456789abcdef' for c in pending_id) and len(pending_id) == 32:
        saved = state_dir() / 'user-decisions' / (pending_id + '.json')
        if saved.is_file() and decision == 'retry':
            pending = json.loads(saved.read_text(encoding='utf-8'))
    if not pending or pending['id'] != pending_id:
        raise BrowserError('PENDING_ID_MISMATCH: run browser status', 64)
    if decision not in ('retry', 'skip') or not note or not note.strip():
        raise BrowserError('Record the actual user reply with --decision retry|skip and --note', 64)
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
        write(state)
        raise BrowserError(str(exc), 2, {**exc.details, **details(state)}) from exc
    if pending:
        clear()
    return result


def execute(args, argv, callback):
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
    if args.command == 'archive' and args.checkpoint and pending:
        if Path(args.checkpoint).resolve() != Path(pending.get('checkpoint') or '.').resolve():
            blocked(pending)
        result = callback()
        clear()
        return result

    def perform(confirmed):
        if confirmed and args.command == 'download':
            args.retry = True
        return callback()
    return run(action(args), argv, perform, recover)
