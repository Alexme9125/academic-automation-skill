"""PubMed records, bounded search, downloads and deterministic bibliography."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import access, ncbi, pmc, browser_runtime as br, interaction, download_watch as dw
from .errors import BrowserError
from .paths import ROOT


def pmid(value):
    value = str(value).strip()
    if value.startswith(('https://', 'http://')):
        url = urlparse(value)
        if url.hostname != 'pubmed.ncbi.nlm.nih.gov': raise BrowserError('Expected PMID or PubMed URL', 64)
        value = url.path.strip('/')
    if not re.fullmatch(r'[1-9]\d{0,8}', value): raise BrowserError('Invalid PMID: ' + value, 64)
    return value


def text(element):
    return ''.join(element.itertext()).strip() if element is not None else ''


def parse_records(root):
    records = {}
    for node in root.findall('PubmedArticle'):
        citation, article = node.find('MedlineCitation'), node.find('MedlineCitation/Article')
        if citation is None or article is None: continue
        ident = citation.findtext('PMID')
        if not ident: continue
        authors = []
        for author in article.findall('AuthorList/Author'):
            authors.append(text(author.find('CollectiveName')) or ' '.join(filter(None, (
                author.findtext('ForeName') or author.findtext('Initials'), author.findtext('LastName'), author.findtext('Suffix')))))
        ids = {x.get('IdType'): text(x) for x in node.findall('PubmedData/ArticleIdList/ArticleId')}
        date = article.find('Journal/JournalIssue/PubDate')
        raw_date = {child.tag: text(child) for child in date} if date is not None else {}
        abstract = [{'label': x.get('Label', ''), 'text': text(x)} for x in article.findall('Abstract/AbstractText')]
        records[ident] = {'pmid': ident, 'href': 'https://pubmed.ncbi.nlm.nih.gov/' + ident + '/',
            'title': text(article.find('ArticleTitle')), 'authors': authors,
            'first_author': authors[0] if authors else '',
            'first_author_family': article.findtext('AuthorList/Author/LastName') or (authors[0] if authors else ''),
            'journal': text(article.find('Journal/Title')), 'journal_abbreviation': article.findtext('Journal/ISOAbbreviation') or '',
            'publication_date': raw_date, 'date': ' '.join(raw_date.values()),
            'article_dates': [{**{x.tag: text(x) for x in d}, 'type': d.get('DateType', '')} for d in article.findall('ArticleDate')],
            'volume': article.findtext('Journal/JournalIssue/Volume') or '', 'issue': article.findtext('Journal/JournalIssue/Issue') or '',
            'pages': article.findtext('Pagination/MedlinePgn') or '-'.join(filter(None, [article.findtext('Pagination/StartPage'), article.findtext('Pagination/EndPage')])) or '',
            'abstract': abstract, 'doi': ids.get('doi', ''), 'pmcid': ids.get('pmc', ''),
            'publication_types': [text(x) for x in article.findall('PublicationTypeList/PublicationType')],
            'relations': [{'type': x.get('RefType', ''), 'pmid': x.findtext('PMID') or '', 'source': x.findtext('RefSource') or ''}
                          for x in citation.findall('CommentsCorrectionsList/CommentsCorrections')],
            'access': 'unknown', 'metadata_source': 'NCBI EFetch'}
    for node in root.findall('PubmedBookArticle'):
        doc = node.find('BookDocument')
        if doc is None or not doc.findtext('PMID'): continue
        ident = doc.findtext('PMID')
        authors = [' '.join(filter(None, (a.findtext('ForeName') or a.findtext('Initials'), a.findtext('LastName'))))
                   or a.findtext('CollectiveName') or '' for a in doc.findall('AuthorList/Author')]
        date = doc.find('Book/PubDate')
        raw_date = {x.tag: text(x) for x in date} if date is not None else {}
        ids = {x.get('IdType'): text(x) for x in doc.findall('ArticleIdList/ArticleId')}
        records[ident] = {'pmid': ident, 'href': 'https://pubmed.ncbi.nlm.nih.gov/' + ident + '/',
            'title': text(doc.find('ArticleTitle')) or text(doc.find('Book/BookTitle')), 'authors': authors,
            'first_author': authors[0] if authors else '', 'first_author_family': doc.findtext('AuthorList/Author/LastName') or '',
            'journal': '', 'book_title': text(doc.find('Book/BookTitle')), 'date': ' '.join(raw_date.values()),
            'publication_date': raw_date, 'doi': ids.get('doi', ''), 'pmcid': ids.get('pmc', ''),
            'abstract': [{'label': x.get('Label', ''), 'text': text(x)} for x in doc.findall('Abstract/AbstractText')],
            'relations': [], 'record_type': 'book', 'access': 'unknown', 'metadata_source': 'NCBI EFetch'}
    return records


def inputs(path):
    raw = Path(path).read_text(encoding='utf-8-sig')
    try: data = json.loads(raw)
    except ValueError: data = [x.strip() for x in raw.splitlines() if x.strip() and not x.lstrip().startswith('#')]
    policy = data.get('access_policy') if isinstance(data, dict) else None
    rows = data.get('rows', []) if isinstance(data, dict) else data
    if not isinstance(rows, list): raise BrowserError('Expected a PMID/URL list or JSON rows', 64)
    ids = [pmid(r.get('pmid') or r.get('href', '')) if isinstance(r, dict) else pmid(r) for r in rows]
    if not ids: raise BrowserError('Empty PubMed input list', 64)
    return list(dict.fromkeys(ids)), policy


def fill(ids, state, cp, publish):
    for ident in ids:
        record = state['records'].get(ident)
        if not record:
            record = parse_records(ncbi.fetch([ident])).get(ident)
            if not record: raise BrowserError('PUBMED_RECORD_MISSING: ' + ident, 3, {'pmid': ident})
            state['records'][ident] = record
            br.atomic_json(cp, state); publish()
        if 'full_text_links' not in record:
            record['full_text_links'] = ncbi.links(ident)
            if any(link['access'] == 'free' for link in record['full_text_links']): record['access'] = 'free'
            br.atomic_json(cp, state); publish()


def search(query, output, pages=1, sort='relevance', free_full_text=False, refresh=False):
    interaction.require_task()
    if not query.strip() or not 1 <= pages <= 500:
        raise BrowserError('Request 1–500 pages (20 records/page); narrow queries for exports over 10,000 records', 64)
    from .search_resume import checkpoint
    filtered = free_full_text or access.current() == 'free-only'
    term = '(' + query + ') AND free full text[sb]' if filtered else query
    config = {'source': 'pubmed', 'query': query, 'sort': sort, 'free_full_text': filtered, 'access_policy': access.current()}
    cp = str(output) + '.progress.json'; state = checkpoint(cp, config, refresh)
    def publish():
        ids = list(dict.fromkeys(i for k in sorted(state['pages'], key=int) if int(k) <= pages for i in state['pages'][k]['ids']))
        rows = [dict(state['records'][i], access_policy=access.current()) for i in ids if i in state['records']]
        result = {**config, 'effective_query': term, 'query_translation': state.get('query_translation', ''),
                  'total': state.get('total'), 'n': len(rows), 'extracted_n': len(rows), 'rows': rows,
                  'complete': all(i in state['records'] and 'full_text_links' in state['records'][i] for i in ids)
                              and (len(state['pages']) >= pages or state.get('exhausted', False)),
                  'checkpoint': str(Path(cp).resolve())}
        br.atomic_json(output, result); return result
    publish()
    for number in range(1, pages + 1):
        page = state['pages'].get(str(number))
        if page is None:
            result = ncbi.search(term, (number - 1) * 20, 20, sort)
            page = {'ids': result.get('idlist', [])}
            expected = min(20, max(0, int(result['count']) - (number - 1) * 20))
            if len(page['ids']) != expected:
                raise BrowserError('PUBMED_INCOMPLETE_PAGE: retry or refresh the query', 70,
                                   {'retryable': True, 'page': number, 'expected': expected, 'received': len(page['ids'])})
            state['pages'][str(number)] = page
            state.update(total=int(result['count']), query_translation=result.get('querytranslation', ''))
            if number * 20 >= state['total']: state['exhausted'] = True
            br.atomic_json(cp, state); publish()
        fill(page['ids'], state, cp, publish)
        if filtered:
            for ident in page['ids']: state['records'][ident].update(access='free', access_evidence='PubMed free full text filter')
            br.atomic_json(cp, state)
        publish()
        if len(page['ids']) < 20 or number * 20 >= state.get('total', 0): break
    return publish()


def metadata(input_path, output, refresh=False):
    interaction.require_task()
    from .search_resume import checkpoint
    ids, policy = inputs(input_path)
    cp = str(output) + '.progress.json'; state = checkpoint(cp, {'source': 'pubmed-metadata'}, refresh)
    def publish():
        result = {'source': 'pubmed', 'requested_pmids': ids, 'access_policy': access.current() or policy,
                  'rows': [state['records'][i] for i in ids if i in state['records']],
                  'complete': all(i in state['records'] and 'full_text_links' in state['records'][i] for i in ids)}
        result['n'] = len(result['rows']); br.atomic_json(output, result); return result
    publish(); fill(ids, state, cp, publish)
    return publish()


def download(value, dest, name='', retry=False):
    interaction.require_task()
    from .cnki import pending_path, resume_download, finish_download
    from . import publisher
    ident = pmid(value)
    # Default uses a stable short PMID filename; user names are bounded for Windows.
    name = dw.safe_name(name or 'PMID-' + ident + '.pdf')
    if not name.lower().endswith('.pdf'): name += '.pdf'
    if len(name.encode('utf-8')) > 180: raise BrowserError('Choose a shorter --name (at most 180 UTF-8 bytes)', 64)
    key = hashlib.sha256(('pubmed\0' + ident + '\0' + str(Path(dest).resolve()) + '\0' + name).encode()).hexdigest()
    cp = pending_path(dest, key)
    done = resume_download(cp, dest, retry=retry, name=name)
    if done: return done
    state = br.read_json(cp, {'source': 'pubmed', 'pmid': ident, 'phase': 'pmc', 'name': name})
    state['access_policy'] = access.current()
    record = state.get('record')
    if not record:
        record = parse_records(ncbi.fetch([ident])).get(ident)
        if not record: raise BrowserError('PUBMED_RECORD_MISSING: ' + ident, 3)
        state['record'] = record; br.atomic_json(cp, state)
    existing = Path(dest) / name
    if existing.exists() and not state.get('file'):
        if not dw.valid_file(existing):
            raise BrowserError('EXISTING_FILE_INVALID: inspect the existing destination before requesting another file', 2,
                               {'checkpoint': str(cp), 'path': str(existing)})
        # Unknown provenance is explicit; content checks run before adopting it.
        state.update(source_url=record['href'], provenance='existing_file_without_download_checkpoint')
        return finish_download(existing, dest, cp, state, name)
    if 'full_text_links' not in record:
        record['full_text_links'] = ncbi.links(ident); br.atomic_json(cp, state)
    try:
        if state['phase'] == 'pmc' and record.get('pmcid'):
            chosen = pmc.select(record, pmc.versions(record['pmcid']), state.get('selected_pmc_version'))
            if chosen:
                state.update(pmc_version=chosen, source_url=chosen['https_url'], text_version=chosen['text_version'])
                br.atomic_json(cp, state)
                path = cp.parent / (cp.stem + '.pdf')
                if pmc.retrieve(chosen, path):
                    record.update(access='free', access_evidence='PMC official public PDF')
                    return finish_download(path, dest, cp, state, name)
                state['pmc_result'] = 'official_pdf_unavailable_or_invalid'
            else: state['pmc_result'] = 'no_distributable_main_pdf'
        state['phase'] = 'publisher'; br.atomic_json(cp, state)
        links = [x for x in record['full_text_links'] if urlparse(x['url']).hostname not in
                 ('pmc.ncbi.nlm.nih.gov', 'www.ncbi.nlm.nih.gov', 'europepmc.org')]
        links.sort(key=lambda x: (x['access'] != 'free', urlparse(x['url']).hostname in ('www.ovid.com', 'ovid.com')))
        final = state.get('publisher_url') or (links[0]['url'] if links else '')
        if not final and record.get('doi'): final = publisher.resolve_doi(record['doi'])
        if not final:
            result = access.unavailable('No official full-text entry; availability unknown')
            state.update(result); br.atomic_json(cp, state)
            return {**result, 'pmid': ident, 'record': record, 'checkpoint': str(cp)}
        state['publisher_url'] = final; br.atomic_json(cp, state)
        free = any(x['url'] == final and x['access'] == 'free' for x in links)
        return {**publisher.article(final, record.get('doi', ''), dest, name, cp, state, free=free),
                'pmid': ident, 'record': record}
    except BrowserError as exc:
        exc.details.update(checkpoint=str(cp), pmid=ident)
        raise


def summary(records, ids):
    selected = [records.get(i, {}) for i in ids]
    from .pdf_verify import WARNING
    archived = [x for x in selected if x.get('code', 0) == 0 and x.get('status') == 'complete' and x.get('path')]
    return {'total': len(ids), 'archived': len(archived),
            'content_verified': sum(bool(x.get('verification', {}).get('content_verified')) for x in archived),
            'pending': sum(not x or x.get('code') in (2, 70, 75) for x in selected),
            'metadata_only': sum(x.get('status') == 'metadata_only' for x in selected),
            'excluded': sum(x.get('status') == 'excluded' for x in selected),
            'skipped_by_user': sum(x.get('code') == 6 for x in selected),
            'access_unknown': sum(x.get('access') == 'unknown' and not x.get('path') for x in selected),
            'failed': sum(x.get('code', 0) not in (0, 2, 6, 70, 75) for x in selected),
            'pdf_verification_note': WARNING if any(not x.get('verification', {}).get('content_verified') for x in archived)
            else 'pypdf optionally checks parsing, page count and first-page title/author; page count alone is not identity proof.'}


def batch(args):
    ids, _ = inputs(args.input)
    if not args.dest: raise BrowserError('PubMed batch requires --dest', 64)
    cp = str(args.input) + '.batch-progress.json'
    state = br.read_json(cp, {'records': {}})
    state.update(initial_pmids=state.get('initial_pmids', ids), requested_pmids=ids, access_policy=args.access_policy)
    state['manifest_changes'] = {'added_pmids': [i for i in ids if i not in state['initial_pmids']],
                                 'removed_pmids': [i for i in state['initial_pmids'] if i not in ids]}
    # Child commands own the lock and the human handoff. Reordering is safe because
    # single-article checkpoints use PMID + destination + name, never list position.
    def publish():
        state['summary'] = summary(state['records'], ids)
        state['rows'] = [dict(state['records'].get(i, {}).get('record', {'pmid': i, 'title': ''}),
                             **{k: v for k, v in state['records'].get(i, {}).items() if k != 'record'}) for i in ids]
        br.atomic_json(cp, state)
    publish()
    order = list(ids)
    pending = interaction.read()
    if pending:
        argv = pending['resume_argv']
        try:
            idx = argv.index('download')
            paused = pmid(argv[idx + 2]) if argv[idx + 1] == 'pubmed' else ''
            if paused not in ids or Path(argv[idx + 3]).resolve() != Path(args.dest).resolve(): interaction.blocked(pending)
            order.remove(paused); order.insert(0, paused)
        except (ValueError, IndexError): interaction.blocked(pending)
    for ident in order:
        cmd = [sys.executable, str(ROOT / 'scripts/academic.py'), '--json', 'download', 'pubmed', ident,
               args.dest, '--access-policy', args.access_policy]
        if args.retry: cmd.append('--retry')
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        try: response = json.loads(proc.stdout)
        except ValueError as exc: raise BrowserError('PUBMED_CHILD_PROTOCOL: ' + proc.stderr[-1000:], 70) from exc
        result = dict(response['result'], code=proc.returncode)
        result.setdefault('status', response.get('status', 'complete' if proc.returncode == 0 else 'failed'))
        state['records'][ident] = result; publish()
        if proc.returncode in (2, 70, 75, 69, 74, 64):
            raise BrowserError(result.get('message', 'PubMed batch paused'), proc.returncode,
                               {**result, 'batch_checkpoint': str(cp), 'summary': state['summary']})
    if state['summary']['failed']:
        raise BrowserError('PubMed batch completed with unavailable or failed records; inspect each status', 1,
                           {'checkpoint': str(cp), **state['summary']})
    return {'checkpoint': str(cp), **state['summary']}


def bibliography(input_path, output, title=None):
    data = br.read_json(input_path)
    if not isinstance(data, dict) or not isinstance(data.get('rows'), list): raise BrowserError('Expected PubMed JSON rows', 64)
    lines = ['# ' + (title or 'PubMed 文献目录'), '', '范围选择：' + str(data.get('access_policy') or '未记录'), '']
    for number, r in enumerate(data['rows'], 1):
        ident = pmid(r['pmid'])
        label = (r.get('title') or 'PMID ' + ident + '（题名待补）').replace('[', '(').replace(']', ')')
        lines += [f"{number}. [{label}](https://pubmed.ncbi.nlm.nih.gov/{ident}/)",
                  '   ' + '; '.join(r.get('authors', [])) + '。' + (r.get('journal') or r.get('book_title', '')) + '，' + r.get('date', '') + '。',
                  '   PMID: ' + ident + ('；DOI: ' + r['doi'] if r.get('doi') else '') + ('；PMCID: ' + r['pmcid'] if r.get('pmcid') else ''),
                  '   全文状态：' + r.get('status', r.get('access', 'unknown')) + '。']
        lines += ['   - 链接：https://pubmed.ncbi.nlm.nih.gov/' + ident + '/']
        if r.get('path'): lines += ['   - 已归档：' + r['path']]
        if r.get('source_url'): lines += ['   - 全文：' + r['source_url']]
        if r.get('verification'):
            v = r['verification']
            lines += ['   - 正文自动核验：' + ('通过' if v.get('content_verified') else '未完成') + '；页数：' + str(v.get('pages'))]
            if v.get('warning'): lines += ['   - ' + v['warning']]
        if r.get('relations'): lines += ['   关联记录：' + '; '.join(x['type'] + ' PMID ' + x['pmid'] for x in r['relations'])]
        lines.append('')
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text('\n'.join(lines), encoding='utf-8')
    return {'output': str(Path(output).resolve()), 'records': len(data['rows'])}
