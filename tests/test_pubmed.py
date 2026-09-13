"""Official-data fixtures and handoff contracts, with no account/network access."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch, Mock
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from academic_automation import access, cli, cnki, ncbi, pmc, pubmed, pdf_verify, publisher, interaction, browser_runtime as br
from academic_automation.errors import BrowserError


def xml(ident='123'):
    return ET.fromstring('''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>ID</PMID><Article>
      <ArticleTitle>Within family <i>Mendelian</i> randomization studies</ArticleTitle>
      <Journal><Title>Human Molecular Genetics</Title><JournalIssue><PubDate><MedlineDate>2019 Oct-Dec</MedlineDate></PubDate></JournalIssue></Journal>
      <AuthorList><Author><LastName>Davies</LastName><ForeName>Neil M</ForeName></Author><Author><CollectiveName>Research Group</CollectiveName></Author></AuthorList>
      <Abstract><AbstractText Label="BACKGROUND">Some text.</AbstractText></Abstract></Article>
      <CommentsCorrectionsList><CommentsCorrections RefType="ErratumIn"><PMID>456</PMID><RefSource>Correction doi:wrong</RefSource></CommentsCorrections></CommentsCorrectionsList>
      </MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1234/original</ArticleId><ArticleId IdType="pmc">PMC123</ArticleId></ArticleIdList></PubmedData>
      </PubmedArticle></PubmedArticleSet>'''.replace('<PMID>ID</PMID>', '<PMID>' + ident + '</PMID>'))


class PubMedTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, {'ACADEMIC_STATE_DIR': str(self.root / 'state'),
            'ACADEMIC_BROWSER_BACKEND': 'extension', 'CNKI_DOWNLOADS_DIR': str(self.root)})
        env.start(); self.addCleanup(env.stop)

    def call(self, args):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream): code = cli.main(['--json', *map(str, args)])
        return code, json.loads(stream.getvalue())['result']

    def record(self): return pubmed.parse_records(xml())['123']

    def version(self, version=1, manuscript=False, pdf=True):
        return {'pmcid': 'PMC123', 'pmid': 123, 'doi': '10.1234/original', 'title': self.record()['title'],
                'version': version, 'is_manuscript': manuscript,
                'pdf_url': f's3://pmc-oa-opendata/PMC123.{version}/PMC123.{version}.pdf' if pdf else None}

    def test_four_sources_stop_before_search_without_access_choice(self):
        for source in ('pubmed', 'cnki-foreign', 'wos', 'scholar'):
            interaction.clear()
            with patch.object(cli, 'dispatch') as dispatch:
                code, result = self.call(['search', source, 'Q', self.root / 'out.json'])
            self.assertEqual(code, 2); dispatch.assert_not_called()
            self.assertEqual(result['pending']['details']['kind'], 'access_policy')

    def test_access_reply_fills_original_task_and_is_not_a_global_default(self):
        args = ['search', 'pubmed', 'Q', self.root / 'out.json']
        code, result = self.call(args); self.assertEqual(code, 2)
        ident = result['pending']['id']
        self.assertEqual(self.call(['browser', 'resolve', '--pending-id', ident, '--decision', 'retry', '--note', 'Only free, keep bibliography'])[0], 64)
        self.assertEqual(self.call(['browser', 'resolve', '--pending-id', ident, '--decision', 'retry', '--note', 'Only free, keep bibliography', '--access-policy', 'free-plus-bib'])[0], 0)
        with patch.object(pubmed, 'search', side_effect=lambda *a: {'policy': access.current()}):
            self.assertEqual(self.call(args), (0, {'policy': 'free-plus-bib'}))
            self.assertEqual(self.call(['search', 'pubmed', 'Different', self.root / 'other.json'])[0], 2)

    def test_policy_classification_does_not_label_unknown_as_paid(self):
        for policy in access.CHOICES:
            with access.scope(policy):
                data = access.classify({'rows': [{'access': 'free'}, {'access': 'unknown'}, {'access': 'subscription'}]})
            self.assertEqual(data['access_policy'], policy)
            self.assertEqual(len(data['rows']), 1 if policy == 'free-only' else 3)
            if policy == 'free-only':
                self.assertEqual(data['unclassified_rows'], [{'access': 'unknown'}])

    def test_ids_reject_other_hosts_and_preserve_order(self):
        self.assertEqual(pubmed.pmid('https://pubmed.ncbi.nlm.nih.gov/37935836/?x=y'), '37935836')
        with self.assertRaises(BrowserError): pubmed.pmid('https://evil.test/37935836/')
        path = self.root / 'ids.txt'; path.write_text('123\nhttps://pubmed.ncbi.nlm.nih.gov/456/\n123\n')
        self.assertEqual(pubmed.inputs(path)[0], ['123', '456'])

    def test_metadata_preserves_dates_authors_abstract_and_original_doi(self):
        record = self.record()
        self.assertEqual(record['doi'], '10.1234/original')
        self.assertEqual(record['relations'][0]['pmid'], '456')
        self.assertEqual(record['authors'], ['Neil M Davies', 'Research Group'])
        self.assertEqual(record['title'], 'Within family Mendelian randomization studies')
        self.assertEqual(record['publication_date'], {'MedlineDate': '2019 Oct-Dec'})
        self.assertEqual(record['abstract'][0]['label'], 'BACKGROUND')

    def test_missing_optional_metadata_remains_empty(self):
        root = ET.fromstring('<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article><ArticleTitle>Title</ArticleTitle></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>')
        record = pubmed.parse_records(root)['1']
        self.assertEqual(record['doi'], ''); self.assertEqual(record['authors'], [])

    def test_search_boolean_query_and_three_policies(self):
        for policy in access.CHOICES:
            out = self.root / (policy + '.json')
            query = 'cancer[Title] OR diabetes[MeSH Terms]'
            with patch.object(ncbi, 'search', return_value={'count': '1', 'idlist': ['123'], 'querytranslation': 'actual translated'}) as search, patch.object(ncbi, 'fetch', return_value=xml()), patch.object(ncbi, 'links', return_value=[]):
                code, result = self.call(['search', 'pubmed', query, out, '--access-policy', policy])
            self.assertEqual(code, 0)
            self.assertEqual(search.call_args.args[0], '(' + query + ') AND free full text[sb]' if policy == 'free-only' else query)
            self.assertEqual(result['query_translation'], 'actual translated')
            self.assertEqual(result['rows'][0]['access'], 'free' if policy == 'free-only' else 'unknown')

    def test_explicit_free_filter_and_date_sort(self):
        with patch.object(ncbi, 'search', return_value={'count': '0', 'idlist': []}) as search:
            code, result = self.call(['search', 'pubmed', 'Q', self.root/'date.json', '--access-policy', 'all', '--sort', 'pub_date', '--free-full-text'])
        self.assertEqual(code, 0); self.assertEqual(search.call_args.args, ('(Q) AND free full text[sb]', 0, 20, 'pub_date'))
        self.assertTrue(result['complete'])

    def test_search_limit_is_checked_without_network(self):
        with patch.object(ncbi, 'search') as search:
            self.assertEqual(self.call(['search', 'pubmed', 'Q', self.root/'a.json', '--pages', '501', '--access-policy', 'all'])[0], 64)
        search.assert_not_called()

    def test_partial_page_resumes_without_refetch_and_paginates(self):
        output = self.root/'search.json'
        args = ['search', 'pubmed', 'Q', output, '--pages', '2', '--access-policy', 'all']
        ids = list(map(str, range(100, 120)))
        calls = [0]
        def fetch(batch):
            calls[0] += 1
            if calls[0] == 2: raise BrowserError('temporary', 70)
            return xml(batch[0])
        with patch.object(ncbi, 'search', return_value={'count': '21', 'idlist': ids}), patch.object(ncbi, 'fetch', side_effect=fetch), patch.object(ncbi, 'links', return_value=[]):
            self.assertEqual(self.call(args)[0], 70)
        self.assertEqual(len(br.read_json(output)['rows']), 1)
        with patch.object(ncbi, 'search', return_value={'count': '21', 'idlist': ['120']}) as search, patch.object(ncbi, 'fetch', side_effect=lambda batch: xml(batch[0])) as fetch, patch.object(ncbi, 'links', return_value=[]):
            code, result = self.call(args)
        self.assertEqual(code, 0); self.assertEqual(result['n'], 21)
        self.assertEqual(search.call_args.args[1], 20)
        self.assertNotIn(['100'], [c.args[0] for c in fetch.call_args_list])

    def test_metadata_reorder_keeps_completed_records(self):
        path = self.root/'list.txt'; out = self.root/'meta.json'; path.write_text('123\n456\n')
        args = ['metadata', path, out, '--source', 'pubmed']
        with patch.object(ncbi, 'fetch', side_effect=[xml(), BrowserError('temporary', 70)]), patch.object(ncbi, 'links', return_value=[]):
            self.assertEqual(self.call(args)[0], 70)
        path.write_text('456\n123\n')
        with patch.object(ncbi, 'fetch', return_value=xml('456')) as fetch, patch.object(ncbi, 'links', return_value=[]):
            code, result = self.call(args)
        self.assertEqual(code, 0); self.assertEqual([r['pmid'] for r in result['rows']], ['456', '123']); fetch.assert_called_once_with(['456'])

    def test_pmc_published_version_precedes_high_number_manuscript(self):
        result = pmc.select(self.record(), [self.version(358, True), self.version()])
        self.assertEqual(result['version'], 1); self.assertEqual(result['text_version'], 'published')

    def test_pmc_manuscript_only_label_and_no_pdf(self):
        self.assertEqual(pmc.select(self.record(), [self.version(3, True)])['text_version'], 'author_manuscript')
        self.assertIsNone(pmc.select(self.record(), [self.version(pdf=False)]))

    def test_pmc_ambiguity_and_supplement_keys_pause(self):
        for versions in ([self.version(), self.version(2)], [self.version(), dict(self.version(2), is_manuscript=None)],
                         [dict(self.version(), pdf_url='s3://pmc-oa-opendata/PMC123.1/supplement.pdf')]):
            with self.assertRaises(BrowserError) as error: pmc.select(self.record(), versions)
            self.assertEqual(error.exception.code, 2)

    def test_pmc_wrong_original_identity_is_not_selected(self):
        self.assertIsNone(pmc.select(self.record(), [dict(self.version(), doi='10.1234/correction')]))

    def test_pmc_html_and_checksum_failure_are_not_archived(self):
        version = pmc.select(self.record(), [self.version()]); path = self.root/'a.pdf'
        with patch.object(ncbi, 'get', return_value=b'<html>challenge</html>'):
            self.assertFalse(pmc.retrieve(version, path)); self.assertFalse(path.exists())
        version['md5'] = 'bad'
        with patch.object(ncbi, 'get', return_value=b'%PDF-1.4 data'):
            with self.assertRaises(BrowserError) as error: pmc.retrieve(version, path)
        self.assertEqual(error.exception.code, 70)

    def test_ncbi_retries_429_and_limits_calls(self):
        response = io.BytesIO(b'{}')
        error = HTTPError('url', 429, 'Too many', {'Retry-After': '1'}, None)
        with patch.object(ncbi, 'urlopen', side_effect=[error, response]) as request, patch.object(ncbi.time, 'sleep') as sleep:
            self.assertEqual(ncbi.get('https://example.org', limited=True), b'{}')
        self.assertEqual(request.call_count, 2); self.assertIn(1.0, [c.args[0] for c in sleep.call_args_list])

    def test_ncbi_network_retry_is_bounded_and_hides_secrets(self):
        with patch.object(ncbi, 'urlopen', side_effect=URLError('secret-token')), patch.object(ncbi.time, 'sleep'):
            with self.assertRaises(BrowserError) as error: ncbi.get('https://example.org?api_key=secret')
        self.assertEqual(error.exception.code, 70); self.assertNotIn('secret', str(error.exception))

    def test_elink_distinguishes_free_subscription_unknown(self):
        root = ET.fromstring('<eLinkResult><ObjUrl><Url>https://free.test/a</Url><Category>Full Text Sources</Category><Attribute>free resource</Attribute></ObjUrl><ObjUrl><Url>https://paid.test/a</Url><Category>Full Text Sources</Category><Attribute>subscription/membership/fee required</Attribute></ObjUrl><ObjUrl><Url>https://unknown.test/a</Url><Category>Full Text Sources</Category></ObjUrl><ObjUrl><Url>https://citation.test/a</Url><Category>Other Literature Sources</Category><Attribute>free resource</Attribute></ObjUrl></eLinkResult>')
        with patch.object(ncbi, 'request', return_value=root):
            self.assertEqual([r['access'] for r in ncbi.links('123')], ['free', 'subscription', 'unknown'])

    def pdf_module(self, page_text='', failure=False):
        page = Mock(); page.extract_text.return_value = page_text
        reader = Mock(return_value=types.SimpleNamespace(pages=[page]))
        if failure: reader.side_effect = ValueError('unparseable')
        return types.SimpleNamespace(PdfReader=reader)

    def test_optional_pdf_missing_parse_failure_and_no_text(self):
        with patch.object(pdf_verify, 'available', return_value=False):
            self.assertEqual(pdf_verify.verify('a.pdf', self.record())['reason'], 'pypdf_not_installed')
        for module, reason in [(self.pdf_module(failure=True), 'pdf_parse_failed'), (self.pdf_module(), 'no_extractable_first_page')]:
            with patch.object(pdf_verify, 'available', return_value=True), patch.dict(sys.modules, {'pypdf': module}):
                self.assertEqual(pdf_verify.verify('a.pdf', self.record())['reason'], reason)

    def test_pdf_title_author_match_and_mismatch(self):
        record = self.record()
        for body, expected in [(record['title'] + '\nNeil Davies\n' + 'Abstract '*20, True), ('A different paper and different authors. '*20, False)]:
            with patch.object(pdf_verify, 'available', return_value=True), patch.dict(sys.modules, {'pypdf': self.pdf_module(body)}):
                if expected: self.assertTrue(pdf_verify.verify('a.pdf', record)['content_verified'])
                else:
                    with self.assertRaises(BrowserError) as error: pdf_verify.verify('a.pdf', record)
                    self.assertEqual(error.exception.code, 2)

    def test_supplement_cannot_pass_by_repeating_title_and_authors(self):
        body = 'Supplementary Information\n' + self.record()['title'] + '\nNeil Davies\n' + 'Details '*30
        with patch.object(pdf_verify, 'available', return_value=True), patch.dict(sys.modules, {'pypdf': self.pdf_module(body)}):
            with self.assertRaises(BrowserError) as error: pdf_verify.verify('a.pdf', self.record())
        self.assertEqual(error.exception.details['verification']['reason'], 'supplement_heading')

    def test_pubmed_book_record_keeps_book_title_separate(self):
        root = ET.fromstring('<PubmedArticleSet><PubmedBookArticle><BookDocument><PMID>99</PMID><ArticleTitle>Chapter</ArticleTitle><Book><BookTitle>A book</BookTitle><PubDate><Year>2025</Year></PubDate></Book><ArticleIdList><ArticleId IdType="doi">10.1234/book</ArticleId></ArticleIdList></BookDocument></PubmedBookArticle></PubmedArticleSet>')
        r = pubmed.parse_records(root)['99']
        self.assertEqual(r['book_title'], 'A book'); self.assertEqual(r['journal'], '')

    def test_pubmed_direct_pmc_download_then_cached_no_network(self):
        args = ['download', 'pubmed', '123', self.root/'中文 空格', '--access-policy', 'free-only']
        def retrieve(version, path): path.write_bytes(b'%PDF-1.4 fixture'); return True
        with patch.object(ncbi, 'fetch', return_value=xml()), patch.object(ncbi, 'links', return_value=[]), patch.object(pmc, 'versions', return_value=[self.version()]), patch.object(pmc, 'retrieve', side_effect=retrieve), patch.object(pdf_verify, 'available', return_value=False), patch.object(br, 'navigate') as navigate:
            code, result = self.call(args)
        self.assertEqual(code, 0); navigate.assert_not_called()
        self.assertEqual(result['sha256'], hashlib.sha256(b'%PDF-1.4 fixture').hexdigest())
        with patch.object(ncbi, 'fetch') as fetch, patch.object(pdf_verify, 'available', return_value=False):
            code, cached = self.call(args)
        self.assertEqual(code, 0); fetch.assert_not_called(); self.assertTrue(cached['cached'])
        self.assertEqual(len(list((self.root/'中文 空格').glob('*.pdf'))), 1)

    def test_publisher_pause_keeps_source_and_manual_file_recovers_first(self):
        args = ['download', 'pubmed', '123', self.root/'out', '--access-policy', 'all']
        links = [{'url': 'https://publisher.test/article', 'access': 'unknown'}]
        with patch.object(ncbi, 'fetch', return_value=xml()), patch.object(ncbi, 'links', return_value=links), patch.object(pmc, 'versions', return_value=[]), patch.object(br, 'read_js', return_value='{}'), patch.object(br, 'navigate', side_effect=BrowserError('CAPTCHA', 2)):
            code, result = self.call(args)
        self.assertEqual(code, 2)
        cp = result['checkpoint']; self.assertEqual(br.read_json(cp)['phase'], 'publisher')
        (self.root/'saved.pdf').write_bytes(b'%PDF-1.4 saved')
        with patch.object(ncbi, 'fetch') as fetch, patch.object(br, 'navigate') as navigate, patch.object(pdf_verify, 'available', return_value=False):
            code, result = self.call(args)
        self.assertEqual(code, 0); fetch.assert_not_called(); navigate.assert_not_called(); self.assertIsNone(interaction.read())

    def test_identity_mismatch_persists_candidate_and_blocks_success(self):
        dest = self.root/'out'; cp = dest/'.academic-downloads/a.json'; path = self.root/'wrong.pdf'; path.write_bytes(b'%PDF-1.4 wrong')
        state = {'source': 'pubmed', 'record': self.record()}
        with patch.object(pdf_verify, 'verify', side_effect=BrowserError('wrong title', 2, {'verification': {'status': 'mismatch'}})):
            with self.assertRaises(BrowserError): cnki.finish_download(path, dest, cp, state)
            with self.assertRaises(BrowserError): cnki.resume_download(cp, dest, retry=True)
        self.assertTrue(path.exists()); self.assertEqual(br.read_json(cp)['status'], 'archiving')

    def test_batch_manifest_scope_and_summary_keeps_all_initial_ids(self):
        path = self.root/'manifest.json'; br.atomic_json(path, {'access_policy': 'free-plus-bib', 'rows': [{'pmid': '123'}, {'pmid': '456'}]})
        results = [subprocess.CompletedProcess([], 0, json.dumps({'result': {'status': 'metadata_only'}}), ''),
                   subprocess.CompletedProcess([], 70, json.dumps({'result': {'message': 'retry'}}), '')]
        with patch.object(pubmed.subprocess, 'run', side_effect=results) as run:
            code, result = self.call(['batch', path, '--source', 'pubmed', '--dest', self.root/'papers'])
        self.assertEqual(code, 70)
        state = br.read_json(str(path) + '.batch-progress.json')
        self.assertEqual(state['initial_pmids'], ['123', '456']); self.assertEqual(state['summary']['total'], 2)
        self.assertIn('free-plus-bib', run.call_args.args[0])

    def test_api_only_doctor_accepts_missing_browser_runtime(self):
        with patch.object(cli, 'doctor', return_value={'runtime_ready': False}):
            self.assertEqual(self.call(['doctor', '--capability', 'pubmed-data'])[0], 0)

    def test_pmc_version_selection_requires_recorded_user_choice(self):
        args = ['download', 'pubmed', '123', self.root/'out', '--access-policy', 'free-only']
        versions = [self.version(), self.version(2)]
        with patch.object(ncbi, 'fetch', return_value=xml()), patch.object(ncbi, 'links', return_value=[]), patch.object(pmc, 'versions', return_value=versions):
            code, result = self.call(args)
        self.assertEqual(code, 2); ident = result['pending']['id']
        resolve = ['browser', 'resolve', '--pending-id', ident, '--decision', 'retry', '--note', 'Use published version 1']
        self.assertEqual(self.call(resolve)[0], 64)
        self.assertEqual(self.call([*resolve, '--pmc-version', '1'])[0], 0)
        self.assertEqual(br.read_json(result['checkpoint'])['selected_pmc_version'], 1)
        self.assertEqual(pmc.select(self.record(), versions, 1)['version'], 1)

    def test_publisher_access_policies_allow_only_confirmed_free_browser_downloads(self):
        from academic_automation import download_capture as capture
        for policy in access.CHOICES:
            dest = self.root/policy; cp = dest/'.academic-downloads/a.json'; cp.parent.mkdir(parents=True)
            candidate = self.root/'capture.pdf'; candidate.write_bytes(b'%PDF-1.4 fixture')
            with access.scope(policy), patch.object(br, 'read_js', side_effect=['{}', 'false']), patch.object(br, 'navigate'), patch.object(br, 'wait_ready'), patch.object(br, 'run_file', return_value='PDF@@https://x.org/main.pdf'), patch.object(publisher, 'direct_pdf', return_value=False), patch.object(capture, 'publisher_control', return_value='a'), patch.object(capture, 'capture', return_value=candidate) as click:
                result = publisher.article('https://x.org/article', '10.1234/a', dest, 'a.pdf', cp, {})
            if policy == 'all': self.assertEqual(result['status'], 'complete'); click.assert_called_once()
            else:
                self.assertEqual(result['status'], 'excluded' if policy == 'free-only' else 'metadata_only')
                self.assertEqual(result['access'], 'unknown'); click.assert_not_called()

    def test_manual_archive_uses_same_pubmed_identity_checks(self):
        dest = self.root/'out'; cp = dest/'.academic-downloads/a.json'; path = self.root/'manual.pdf'; path.write_bytes(b'%PDF-1.4 manual')
        br.atomic_json(cp, {'status': 'waiting', 'source': 'pubmed', 'record': self.record()})
        with patch.object(pdf_verify, 'verify', return_value={'content_verified': True}) as verify:
            code, result = self.call(['archive', dest, '--file', path, '--checkpoint', cp])
        self.assertEqual(code, 0); verify.assert_called_once(); self.assertTrue(result['verification']['content_verified'])

    def test_copy_corruption_keeps_source(self):
        from academic_automation import download_watch as dw
        source = self.root/'a.pdf'; source.write_bytes(b'%PDF-1.4 original')
        with patch.object(dw.shutil, 'copyfileobj', side_effect=lambda src, dest: dest.write(b'%PDF-1.4 broken')):
            with self.assertRaises(BrowserError): dw.archive(source, self.root/'out')
        self.assertTrue(source.exists()); self.assertEqual(list((self.root/'out').iterdir()), [])

    def test_changed_archive_pauses_instead_of_redownloading(self):
        source = self.root/'a.pdf'; source.write_bytes(b'%PDF-1.4 original')
        dest = self.root/'out'; cp = dest/'.academic-downloads/a.json'
        with patch.object(pdf_verify, 'available', return_value=False):
            result = cnki.finish_download(source, dest, cp, {'source': 'pubmed', 'record': self.record()})
        Path(result['path']).write_bytes(b'%PDF-1.4 changed')
        with self.assertRaises(BrowserError) as error: cnki.resume_download(cp, dest, retry=True)
        self.assertEqual(error.exception.code, 2)
        counts = pubmed.summary({'123': {'path': result['path'], 'code': 2, 'status': 'needs_user'}}, ['123'])
        self.assertEqual(counts['archived'], 0); self.assertEqual(counts['pending'], 1)

    def test_long_windows_filename_rejected_before_network(self):
        with patch.object(ncbi, 'fetch') as fetch:
            code, _ = self.call(['download', 'pubmed', '123', self.root/'out', '--name', '中'*100, '--access-policy', 'all'])
        self.assertEqual(code, 64); fetch.assert_not_called()

    def test_pmc_listing_is_article_scoped_and_follows_pagination(self):
        one = b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Contents><Key>metadata/PMC123.1.json</Key></Contents><IsTruncated>true</IsTruncated><NextContinuationToken>next</NextContinuationToken></ListBucketResult>'
        two = b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Contents><Key>metadata/PMC123.2.json</Key></Contents><IsTruncated>false</IsTruncated></ListBucketResult>'
        with patch.object(ncbi, 'get', side_effect=[one, json.dumps(self.version()).encode(), two, json.dumps(self.version(2)).encode()]) as get:
            self.assertEqual(len(pmc.versions('PMC123')), 2)
        self.assertIn('prefix=metadata%2FPMC123.', get.call_args_list[0].args[0])
        self.assertIn('continuation-token=next', get.call_args_list[2].args[0])

    def test_bibliography_preserves_related_record_and_source_links(self):
        path = self.root/'records.json'; br.atomic_json(path, {'access_policy': 'all', 'rows': [self.record()]})
        output = self.root/'bibliography.md'
        self.assertEqual(self.call(['bibliography', 'pubmed', path, output])[0], 0)
        body = output.read_text(); self.assertIn('https://pubmed.ncbi.nlm.nih.gov/123/', body)
        self.assertIn('ErratumIn PMID 456', body); self.assertIn('10.1234/original', body)


if __name__ == '__main__': unittest.main()
