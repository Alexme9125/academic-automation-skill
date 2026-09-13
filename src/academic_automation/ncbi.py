"""Small, rate-limited NCBI client. No browser state or third-party dependency."""
import json
import os
import time
from http.client import HTTPException, IncompleteRead
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .browser_runtime import atomic_json, read_json
from .errors import BrowserError
from .paths import state_dir

BASE = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'


def get(url, limited=False):
    for attempt in range(3):
        if limited:
            # Public workflow calls hold the shared process lock. Persist the last
            # request to also limit adjacent short-lived CLI processes to 3/sec.
            from .browser import browser_lock
            with browser_lock('ncbi-rate'):
                stamp = state_dir() / 'ncbi-last-request.json'
                delay = .35 - (time.time() - read_json(stamp, {}).get('time', 0))
                if delay > 0: time.sleep(min(delay, .35))
                atomic_json(stamp, {'time': time.time()})
        try:
            with urlopen(Request(url, headers={'User-Agent': 'academic-automation/2 PubMed integration'}), timeout=30) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504):
                raise BrowserError('NCBI_HTTP_ERROR: ' + str(exc.code), 70,
                                   {'http_status': exc.code, 'retryable': exc.code >= 500}) from exc
            retry = exc.headers.get('Retry-After', '') if exc.headers else ''
            delay = float(retry) if retry.isdigit() else 2 ** attempt
            if delay > 10 or attempt == 2:
                raise BrowserError('NCBI_RATE_OR_SERVICE_ERROR: retry this task later', 70,
                                   {'http_status': exc.code, 'retry_after': delay, 'retryable': True}) from exc
            time.sleep(delay)
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            if attempt == 2:
                # Do not print a URL that may contain an API key or email.
                details = {'retryable': True, 'attempts': attempt + 1}
                if isinstance(exc, IncompleteRead):
                    details.update(received_bytes=len(exc.partial), missing_bytes=exc.expected)
                raise BrowserError('NCBI_NETWORK_ERROR: retry this task later', 70, details) from exc
            time.sleep(2 ** attempt)


def request(operation, **params):
    params.update(tool='academic_automation')
    for key, env in (('api_key', 'NCBI_API_KEY'), ('email', 'NCBI_EMAIL')):
        if os.environ.get(env): params[key] = os.environ[env]
    raw = get(BASE + operation + '.fcgi?' + urlencode(params, doseq=True), limited=True)
    try:
        result = json.loads(raw) if params.get('retmode') == 'json' else ET.fromstring(raw)
    except (ValueError, ET.ParseError) as exc:
        raise BrowserError('NCBI_PROTOCOL: response is not the requested data format', 70, {'retryable': True}) from exc
    if isinstance(result, dict):
        error = result.get('error') or result.get('esearchresult', {}).get('ERROR')
    else:
        error = result.findtext('.//ERROR')
    if error:
        raise BrowserError('NCBI_QUERY_ERROR: ' + str(error), 64)
    return result


def search(term, start=0, count=20, sort='relevance'):
    return request('esearch', db='pubmed', term=term, retstart=start, retmax=count,
                   sort=sort, retmode='json')['esearchresult']


def fetch(ids):
    return request('efetch', db='pubmed', id=','.join(ids), retmode='xml')


def links(pmid):
    root = request('elink', dbfrom='pubmed', id=pmid, cmd='llinks', retmode='xml')
    found = []
    for item in root.findall('.//ObjUrl'):
        categories = [x.text or '' for x in item.findall('Category')]
        if 'Full Text Sources' not in categories: continue
        url = item.findtext('Url') or ''
        attrs = [x.text or '' for x in item.findall('Attribute')]
        # LinkOut carries free/subscription properties; keep unknown distinct.
        free = any(x.lower() == 'free resource' or 'free full text' in x.lower() for x in attrs)
        subscription = any('subscription' in x.lower() for x in attrs)
        if url.startswith(('http://', 'https://')):
            found.append({'url': url, 'provider': item.findtext('Provider/Name') or '',
                          'categories': categories, 'attributes': attrs,
                          'access': 'free' if free else 'subscription' if subscription else 'unknown'})
    return list({x['url']: x for x in found}.values())
