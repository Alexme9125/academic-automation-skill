"""One trusted browser click; a missing event never causes another click."""
import json
import re
import uuid
from pathlib import Path

from . import browser_runtime as br, download_watch as dw
from .errors import BrowserError


def capture(checkpoint, state, selector, author=''):
    folder = Path(checkpoint).parent / (Path(checkpoint).stem + '.transfers') / uuid.uuid4().hex
    folder.mkdir(parents=True)
    transfer = folder / 'received.part'
    state['transfer_file'] = str(transfer)
    br.atomic_json(checkpoint, state)
    try:
        # Compatibility method delegates to the same general capture transport.
        event = br.get_browser().cnki_download(selector, transfer)
        state['download_event'] = event
    except BrowserError as exc:
        state['download_event'] = {'status': 'transport_error', 'error': str(exc)}
        br.atomic_json(checkpoint, state)
        if exc.code not in (2, 70): raise
        event = state['download_event']
    br.atomic_json(checkpoint, state)
    if event.get('status', '').startswith('needs_'):
        kind = event['status']
        message = {'needs_consent': 'Choose and dismiss the Cookie/consent dialog; the download button has not been clicked',
                   'needs_control': 'The download control is not actionable; inspect its visibility or overlay. It has not been clicked',
                   'needs_foreground': 'Make the bound task tab visible; the download button has not been clicked',
                   'needs_verification': 'Complete login or verification in the current tab; the download button has not been clicked'}
        raise BrowserError('NEEDS_USER: ' + message.get(kind, 'Inspect the current page'), 2,
                           {'kind': kind, 'checkpoint': str(checkpoint), 'diagnostics': event})
    if not event.get('saved'): return None
    original = dw.safe_name(event.get('suggested_filename') or 'article.pdf')
    if author and not re.search('_' + re.escape(author) + r'(?:\s*\(\d+\))?\.(?:pdf|caj)$', original, re.I):
        raise BrowserError('NEEDS_USER: captured filename does not match the expected author; verify the file', 2,
                           {'checkpoint': str(checkpoint), 'suggested_filename': original, 'transfer_file': str(transfer)})
    suffix = Path(original).suffix.lower() if author else '.pdf'
    saved = folder / ('received' + suffix)
    state.update(candidate=str(saved), suggested_filename=original)
    if author: state['name'] = original
    br.atomic_json(checkpoint, state)
    transfer.replace(saved)
    if not dw.valid_file(saved):
        raise BrowserError('NEEDS_USER: captured file is not a valid PDF/CAJ', 2, {'checkpoint': str(checkpoint)})
    return saved


def publisher_control(url):
    token = uuid.uuid4().hex
    script = '''(function(){const target=new URL(__URL__,location.href).href;
      const links=Array.from(document.querySelectorAll('a[href]')).filter(a=>a.href===target && a.getClientRects().length);
      let a=links[0];
      if(!a){a=document.createElement('a');a.href=target;a.textContent='Download article PDF';document.body.appendChild(a);}
      a.setAttribute('data-academic-pdf',__TOKEN__);return 'selected';})()'''
    br.run_js(script.replace('__URL__', json.dumps(url)).replace('__TOKEN__', json.dumps(token)))
    return '[data-academic-pdf="' + token + '"]'
