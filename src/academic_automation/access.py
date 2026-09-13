"""Per-task literature scope. Never infer consent from an earlier unrelated task."""
from contextlib import contextmanager
from contextvars import ContextVar

from .errors import BrowserError
from .paths import state_dir
from .browser_runtime import atomic_json, read_json

CHOICES = ('all', 'free-only', 'free-plus-bib')
_policy = ContextVar('literature_access', default=None)


def current():
    return _policy.get()


@contextmanager
def scope(policy):
    token = _policy.set(policy)
    try:
        yield
    finally:
        _policy.reset(token)


def required(args):
    source = getattr(args, 'source', '')
    return ((args.command == 'search' and source in ('pubmed', 'cnki-foreign', 'wos', 'scholar'))
            or (args.command == 'download' and source in ('pubmed', 'doi'))
            or (args.command == 'batch' and source == 'pubmed'))


def decision_path(key):
    return state_dir() / 'access-decisions' / (key + '.json')


def save(key, policy):
    if policy not in CHOICES:
        raise BrowserError('Choose --access-policy all|free-only|free-plus-bib', 64)
    atomic_json(decision_path(key), {'access_policy': policy})


def prepare(args, key):
    if not required(args):
        return getattr(args, 'access_policy', None)
    policy = getattr(args, 'access_policy', None)
    if not policy and args.command == 'batch':
        manifest = read_json(args.input)
        policy = manifest.get('access_policy') if isinstance(manifest, dict) else None
    if not policy:
        policy = read_json(decision_path(key), {}).get('access_policy')
    if policy not in CHOICES:
        raise BrowserError('ACCESS_POLICY_REQUIRED: 是否考虑付费或订阅文献？若不考虑，再询问这些文献是放弃还是保留题录。', 2,
                           {'kind': 'access_policy', 'choices': list(CHOICES),
                            'question': '是否考虑付费或订阅文献？',
                            'followup_if_declined': '这些文献是放弃，还是保留题录？'})
    args.access_policy = policy
    save(key, policy)
    return policy


def public_only():
    return current() in ('free-only', 'free-plus-bib')


def unavailable(reason, access='unknown'):
    if access == 'unknown':
        raise BrowserError('ACCESS_UNKNOWN: ' + reason, 2,
                           {'kind': 'access_unknown', 'access': 'unknown', 'access_policy': current(),
                            'next_action': 'Keep this article pending. Ask the user to inspect article-level free-access evidence, '
                                           'or explicitly choose bibliography, skip or replacement. Unknown is not subscription.'})
    return {'status': 'excluded' if current() == 'free-only' else 'metadata_only',
            'access_policy': current(), 'access': access, 'reason': reason}


def classify(data):
    """Keep uncertain availability separate; a missing OA label does not mean paid."""
    policy = current()
    if not policy or not isinstance(data, dict):
        return data
    rows = data.get('rows', [])
    if policy == 'free-only':
        included, unknown, excluded = [], [], []
        for row in rows:
            if row.get('access') == 'free': included.append(row)
            elif row.get('access') == 'subscription': excluded.append(row)
            else: unknown.append(row)
        data.update(rows=included, unclassified_rows=unknown, excluded_rows=excluded,
                    extracted_n=len(rows), n=len(included))
        data['classification_complete'] = not unknown
        data['access_note'] = ('No reliable free-access evidence for unclassified_rows; do not label these paid or silently discard them.'
                               if unknown else 'Included records have free-access evidence; excluded rows are recorded separately.')
    data['access_policy'] = policy
    return data
