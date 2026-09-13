"""Auditable human resolution of a specific, otherwise complete PDF ambiguity."""
import hashlib
import re
import time
from pathlib import Path

from . import browser_runtime as br, cnki, download_watch as dw, interaction, pdf_verify
from .errors import BrowserError
from .paths import state_dir


def archive(args, state):
    if (not args.pending_id or not re.fullmatch(r'[0-9a-f]{32}', args.pending_id)
            or not args.sha256 or not re.fullmatch(r'[0-9a-f]{64}', args.sha256)
            or not args.note or not args.note.strip()):
        raise BrowserError('MANUAL_IDENTITY_ARGUMENTS: supply the pending id, SHA-256 and actual user reply', 64)
    pending = interaction.read()
    if not pending:
        pending = br.read_json(state_dir() / 'user-decisions' / (args.pending_id + '.json'), {})
    if (not pending or pending['id'] != args.pending_id or
            Path(pending.get('checkpoint') or '.').resolve() != Path(args.checkpoint).resolve()):
        raise BrowserError('PENDING_ID_MISMATCH: manual review must belong to this checkpoint', 64)
    path = Path(state['file']['path'] if state.get('status') == 'complete' and state.get('file') else args.file)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != args.sha256 or digest != state.get('candidate_sha256'):
        raise BrowserError('MANUAL_IDENTITY_FILE_CHANGED: review the exact candidate and SHA-256 again', 2)
    if not dw.valid_file(path): raise BrowserError('INVALID_DOWNLOAD: manual identity cannot waive file integrity', 2)
    record = state.get('record') or {'title': state.get('title', ''), 'first_author': state.get('author', '')}
    try:
        pdf_verify.verify(path, record)
    except BrowserError as exc:
        if exc.details.get('kind') != 'identity_review': raise
    else:
        raise BrowserError('MANUAL_IDENTITY_NOT_NEEDED: use normal archive for a verified or unverified file', 64)
    state['manual_identity'] = {'sha256': digest, 'identity_key': pdf_verify.identity_key(record),
        'pmid': state.get('pmid', record.get('pmid')), 'pending_id': pending['id'],
        'note': args.note.strip(), 'confirmed_at': time.time(), 'pages': state.get('verification', {}).get('pages')}
    # Journal before archiving: a crash can recover this exact user-approved file.
    br.atomic_json(args.checkpoint, state)
    result = (cnki.resume_download(args.checkpoint, args.dest) if state.get('status') == 'complete'
              else cnki.finish_download(path, args.dest, args.checkpoint, state, args.name or state.get('name', '')))
    pending['user_decision'] = {'decision': 'confirm_identity', 'note': args.note.strip(), 'time': time.time(), 'sha256': digest}
    br.atomic_json(state_dir() / 'user-decisions' / (pending['id'] + '.json'), pending)
    (state_dir() / 'skipped-actions' / (pending['action'] + '.json')).unlink(missing_ok=True)
    return result
