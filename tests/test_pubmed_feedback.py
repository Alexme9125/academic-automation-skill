"""Offline reproductions of the September 14 macOS tester's six findings."""
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import Mock, patch

from pdf_fixture import PDF, pdf_bytes
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from academic_automation import access, browser, cli, cnki, http_pdf, interaction, ncbi, native_save, pdf_verify, pmc, publisher, pubmed
from academic_automation import browser_runtime as br
from academic_automation.errors import BrowserError


class Response(io.BytesIO):
    def __init__(self, body=PDF, headers=None, status=200):
        super().__init__(body)
        self.headers = {'Content-Length': str(len(body)), **(headers or {})}; self.status = status


class PubMedFeedbackTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        env = patch.dict(os.environ, {'ACADEMIC_STATE_DIR': str(self.root/'state'),
            'CNKI_DOWNLOADS_DIR': str(self.root/'downloads'), 'ACADEMIC_BROWSER_BACKEND': 'apple-events',
            'ACADEMIC_BROWSER_SESSION': 'feedback'})
        env.start(); self.addCleanup(env.stop); (self.root/'downloads').mkdir()
        self.dest = self.root/'中文 papers'; self.cp = self.dest/'.academic-downloads/test.json'

    def call(self, args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out): code = cli.main(['--json', *map(str, args)])
        return code, json.loads(out.getvalue())['result']

    def test_ncbi_incomplete_read_has_bounded_retries_and_structured_bytes(self):
        def response(*a, **k):
            r = Response(); r.read = Mock(side_effect=IncompleteRead(b'partial', 8)); return r
        with patch.object(ncbi, 'urlopen', side_effect=response) as get, patch.object(ncbi.time, 'sleep'):
            with self.assertRaises(BrowserError) as error: ncbi.get('https://example.test/?api_key=private')
        self.assertEqual(get.call_count, 3); self.assertEqual(error.exception.code, 70)
        self.assertEqual(error.exception.details['received_bytes'], 7)
        self.assertNotIn('private', str(error.exception))

    def test_cli_unexpected_http_exception_still_returns_json(self):
        with patch.object(pubmed, 'download', side_effect=IncompleteRead(b'x', 2)):
            code, result = self.call(['download', 'pubmed', '123', self.dest, '--access-policy', 'free-only'])
        self.assertEqual(code, 70); self.assertTrue(result['retryable'])

    def test_range_resume_requires_etag_and_reuses_verified_prefix(self):
        target = self.root/'paper.pdf'; cut = len(PDF)-30
        with patch.object(http_pdf, 'urlopen', side_effect=[Response(PDF[:cut], {'Content-Length':str(len(PDF)), 'ETag':'"v1"'}),
                 Response(PDF[cut:], {'Content-Range':f'bytes {cut}-{len(PDF)-1}/{len(PDF)}', 'ETag':'"v1"'}, 206)]) as get, patch.object(http_pdf.time, 'sleep'):
            result = http_pdf.fetch('https://x.test/paper.pdf', target, md5=hashlib.md5(PDF).hexdigest())
        self.assertEqual(result['status'], 'complete'); self.assertEqual(target.read_bytes(), PDF)
        self.assertEqual(get.call_args.args[0].get_header('Range'), f'bytes={cut}-')
        self.assertEqual(result['resumed_bytes'], cut)

    def test_range_ignored_restarts_without_concatenating_or_deleting_prefix(self):
        target = self.root/'paper.pdf'
        with patch.object(http_pdf, 'urlopen', side_effect=[Response(PDF[:-20], {'Content-Length':str(len(PDF)), 'ETag':'"v1"'}), Response(PDF, {'ETag':'"v2"'})]), patch.object(http_pdf.time, 'sleep'):
            result = http_pdf.fetch('https://x.test/paper.pdf', target)
        self.assertEqual(result['status'], 'complete'); self.assertEqual(target.read_bytes(), PDF)
        history = br.read_json(str(target)+'.http.json')
        self.assertTrue(Path(history[0]['part']).exists()); self.assertEqual(result['resumed_bytes'], 0)

    def test_range_wrong_validator_or_offset_never_promotes(self):
        for etag, start in [('"other"', len(PDF)-20), ('"v1"', 1)]:
            target = self.root/(str(start)+etag.replace('"','')+'.pdf')
            with patch.object(http_pdf, 'urlopen', side_effect=[Response(PDF[:-20], {'Content-Length':str(len(PDF)), 'ETag':'"v1"'}),
                     Response(PDF[-20:], {'Content-Range':f'bytes {start}-{len(PDF)-1}/{len(PDF)}', 'ETag':etag}, 206)]), patch.object(http_pdf.time, 'sleep'):
                result = http_pdf.fetch('https://x.test/paper.pdf', target)
            self.assertEqual(result['error'], 'unexpected_response'); self.assertFalse(target.exists())
            self.assertFalse(br.read_json(str(target)+'.transfer.json').get('etag'))

    def test_partial_tampering_causes_fresh_request(self):
        target = self.root/'paper.pdf'
        with patch.object(http_pdf, 'urlopen', return_value=Response(PDF[:-20], {'Content-Length':str(len(PDF)), 'ETag':'"v1"'})):
            result = http_pdf.fetch('https://x.test/paper.pdf', target, attempts=1)
        Path(result['part']).write_bytes(b'changed')
        with patch.object(http_pdf, 'urlopen', return_value=Response()) as get:
            self.assertEqual(http_pdf.fetch('https://x.test/paper.pdf', target)['status'], 'complete')
        self.assertIsNone(get.call_args.args[0].get_header('Range'))

    def test_transfer_deadline_stops_a_slow_reader(self):
        ticks = iter(range(100)); target = self.root/'paper.pdf'
        with patch.object(http_pdf.time, 'monotonic', side_effect=lambda: next(ticks)), patch.object(http_pdf, 'urlopen', return_value=Response()) as get:
            result = http_pdf.fetch('https://x.test/paper.pdf', target, max_seconds=2)
        self.assertEqual(result['error'], 'transfer_deadline'); self.assertEqual(get.call_count, 1)
        self.assertFalse(target.exists()); self.assertTrue(Path(result['progress']).is_file())

    def test_pmc_stream_error_keeps_structured_progress(self):
        with patch.object(http_pdf, 'urlopen', side_effect=lambda *a,**k: Response(PDF[:-20], {'Content-Length':str(len(PDF))})), patch.object(http_pdf.time, 'sleep'):
            with self.assertRaises(BrowserError) as error: pmc.retrieve({'https_url':'https://x.test/a.pdf'}, self.root/'a.pdf')
        self.assertEqual(error.exception.code, 70); self.assertTrue(error.exception.details['retryable'])
        self.assertTrue(Path(error.exception.details['part']).is_file())

    def pause_browser(self):
        with patch.object(publisher, 'download', side_effect=BrowserError('NEED_CONNECTION: stale tab', 2)):
            code, result = self.call(['download','doi','10.1234/a',self.dest,'--access-policy','all'])
        self.assertEqual(code, 2); return result['pending']

    def test_api_search_runs_with_browser_lock_and_pending_untouched(self):
        pending = self.pause_browser()
        with browser.browser_lock(), patch.object(pubmed, 'search', return_value={'n':0}) as search:
            code, result = self.call(['search','pubmed','Q',self.root/'out.json','--access-policy','free-only'])
        self.assertEqual(code, 0); search.assert_called_once(); self.assertEqual(interaction.read()['id'], pending['id'])
        with patch.object(pubmed,'metadata',return_value={'n':0}) as metadata:
            self.assertEqual(self.call(['metadata',self.root/'in',self.root/'out','--source','pubmed'])[0],0)
        metadata.assert_called_once(); self.assertEqual(interaction.read()['id'], pending['id'])

    def test_api_choices_are_separate_from_browser_and_other_api_task(self):
        browser_pending = self.pause_browser(); ids=[]
        for query in ('first','second'):
            code, result = self.call(['search','pubmed',query,self.root/(query+'.json')]); self.assertEqual(code,2)
            ids.append(result['pending']['id'])
        self.assertNotEqual(ids[0],ids[1]); self.assertEqual(len(interaction.api_pending()),2)
        self.assertEqual(self.call(['browser','resolve','--pending-id',ids[0],'--decision','retry','--access-policy','free-only','--note','Test user selected only free'])[0],0)
        with patch.object(pubmed,'search',return_value={'n':0}):
            self.assertEqual(self.call(['search','pubmed','first',self.root/'first.json'])[0],0)
        self.assertEqual(interaction.read()['id'],browser_pending['id']); self.assertEqual(len(interaction.api_pending()),1)

    def test_connection_recovery_requires_reply_and_explicit_rebind(self):
        pending = self.pause_browser()
        with patch.object(browser,'get_browser') as transport:
            code,result=self.call(['browser','connect']); self.assertEqual(code,2); transport.assert_not_called()
        self.assertIn('browser connect',result['next_action'])
        self.call(['browser','resolve','--pending-id',pending['id'],'--decision','retry','--note','Test user opened the article tab'])
        with patch.object(browser,'get_browser') as transport:
            transport.return_value.connect.return_value={'connected':True}
            self.assertEqual(self.call(['browser','connect'])[0],0); transport.return_value.connect.assert_called_once()
        self.assertEqual(interaction.read()['id'],pending['id'])

    def glyph_case(self):
        title="Anti-inflammatory CAR-microglia targeting Aβ for Alzheimer's disease therapy"
        record={'pmid':'123','doi':'10.1234/a','title':title,'first_author':'Xizhong Ding','first_author_family':'Ding','authors':['Xizhong Ding']}
        text=title.replace('β','b')+'\nXizhong Ding\n10.1234/a\n'+'Abstract '*30
        path=self.root/'glyph.pdf'; path.write_bytes(pdf_bytes(text))
        fake=types.SimpleNamespace(PdfReader=lambda path:types.SimpleNamespace(pages=[types.SimpleNamespace(extract_text=lambda:text)]))
        stack=contextlib.ExitStack(); self.addCleanup(stack.close)
        stack.enter_context(patch.object(pdf_verify,'available',return_value=True)); stack.enter_context(patch.dict(sys.modules,{'pypdf':fake}))
        def download(*a,**k): return cnki.finish_download(path,self.dest,self.cp,{'record':record,'pmid':'123','name':'PMID-123.pdf'})
        args=['download','pubmed','123',self.dest,'--access-policy','free-only']
        with patch.object(pubmed,'download',side_effect=download):code,result=self.call(args)
        self.assertEqual(code,2); self.assertEqual(result['kind'],'identity_review')
        return path, record, result, args

    def test_manual_glyph_review_archives_and_cached_resume_keeps_separate_count(self):
        path,record,result,args=self.glyph_case(); digest=hashlib.sha256(path.read_bytes()).hexdigest()
        command=['archive',self.dest,'--file',path,'--checkpoint',self.cp,'--confirm-identity','--pending-id',result['pending']['id'],'--sha256',digest,'--note','Test user checked the title, authors and DOI']
        code,saved=self.call(command); self.assertEqual(code,0,saved); self.assertIsNone(interaction.read())
        self.assertTrue(saved['verification']['manually_verified']); self.assertFalse(saved['verification']['content_verified'])
        self.assertEqual(self.call(command)[0],0)
        with patch.object(cnki,'pending_path',return_value=self.cp),patch.object(ncbi,'fetch') as fetch:
            code,cached=self.call(args)
        self.assertEqual(code,0,cached); self.assertTrue(cached['cached']); fetch.assert_not_called()
        counts=pubmed.summary({'123':cached},['123'])
        self.assertEqual((counts['archived'],counts['content_verified'],counts['manually_verified']),(1,0,1))
        with patch.object(pdf_verify,'available',return_value=False):
            self.assertTrue(cnki.resume_download(self.cp,self.dest)['verification']['manually_verified'])

    def test_manual_confirmation_rejects_changed_file_or_missing_reply(self):
        path,record,result,args=self.glyph_case()
        command=['archive',self.dest,'--file',path,'--checkpoint',self.cp,'--confirm-identity','--pending-id',result['pending']['id'],'--sha256',hashlib.sha256(path.read_bytes()).hexdigest()]
        self.assertEqual(self.call(command)[0],64)
        path.write_bytes(PDF)
        self.assertEqual(self.call(command+['--note','Test user checked prior file'])[0],2)
        self.assertFalse((self.dest/'PMID-123.pdf').exists())

    def test_manual_identity_approval_is_invalid_for_changed_metadata(self):
        path,record,result,args=self.glyph_case()
        approval={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'identity_key':pdf_verify.identity_key(record),'note':'Test reply','pending_id':result['pending']['id']}
        self.assertTrue(pdf_verify.verify(path,record,approval)['manually_verified'])
        with self.assertRaises(BrowserError):pdf_verify.verify(path,dict(record,doi='10.1234/other'),approval)

    def test_manual_review_can_finish_an_old_skipped_candidate(self):
        path,record,result,args=self.glyph_case();ident=result['pending']['id']
        self.call(['browser','resolve','--pending-id',ident,'--decision','skip','--note','Test user retained file pending review'])
        code,saved=self.call(['archive',self.dest,'--file',path,'--checkpoint',self.cp,'--confirm-identity',
            '--pending-id',ident,'--sha256',hashlib.sha256(path.read_bytes()).hexdigest(),'--note','Test user now confirms title, author and DOI'])
        self.assertEqual(code,0,saved)
        self.assertFalse((self.root/'state/skipped-actions'/ (result['pending']['action']+'.json')).exists())

    def test_wrong_doi_access_evidence_never_clicks(self):
        state={'record':{'doi':'10.1234/right'},'pdf_links':['https://wiley.test/main.pdf']}
        with access.scope('free-only'),patch.object(br,'read_js',side_effect=['{"url":"https://wiley.test/article"}','{"access":"free","doi":"10.1234/wrong"}']),patch.object(br,'wait_ready'),patch.object(publisher,'direct_pdf',return_value=False),patch.object(br,'run_js') as click:
            with self.assertRaises(BrowserError) as error: publisher.article('https://wiley.test/article','10.1234/right',self.dest,'main.pdf',self.cp,state)
        self.assertIn('IDENTITY_MISMATCH',str(error.exception));click.assert_not_called()

    def test_article_access_script_accepts_scoped_evidence_not_menu_text(self):
        script=ROOT/'scripts/pub/access.js'
        fixture=r'''
const fs=require('fs'), vm=require('vm');
const source=fs.readFileSync(process.argv[1],'utf8');
function run(kind) {
  const node={innerText:'Open Access', content:'https://creativecommons.org/licenses/by/4.0/',getClientRects:()=>[1]};
  const document={body:{innerText:'Open Access'},querySelector:()=>({content:'10.1234/a'}),
    querySelectorAll:(selector)=> kind==='article' && selector.includes('.doi-access') ? [node] :
      kind==='license' && selector.includes('meta[name="dc.Rights"]') ? [node] : []};
  return JSON.parse(vm.runInNewContext(source,{document,Array,getComputedStyle:()=>({visibility:'visible'})}));
}
process.stdout.write(JSON.stringify(['menu','article','license'].map(run)));
'''
        proc=subprocess.run(['node','-e',fixture,str(script)],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual([r['access'] for r in json.loads(proc.stdout)],['unknown','free','free'])

    def test_batch_child_timeout_retains_article_and_metadata(self):
        manifest=self.root/'manifest.json';br.atomic_json(manifest,{'access_policy':'free-only','rows':[{'pmid':'123','title':'Known title'}]})
        with patch.object(pubmed.subprocess,'run',side_effect=subprocess.TimeoutExpired('child',600)):
            code,result=self.call(['batch',manifest,'--source','pubmed','--dest',self.dest])
        self.assertEqual(code,70);self.assertEqual(result['summary']['pending'],1)
        state=br.read_json(str(manifest)+'.batch-progress.json')
        self.assertEqual(state['rows'][0]['title'],'Known title')

    def test_jama_redirect_accepts_only_known_article_pdf_and_identical_filename(self):
        source='https://jamanetwork.com/journals/jamanetworkopen/articlepdf/2851652/ng_2026_oi.pdf'
        self.assertTrue(native_save.same_pdf_target(source,'https://watermark02.silverchair.com/ng_2026_oi.pdf?fixture=1'))
        for actual in ['https://watermark02.silverchair.com/wrong.pdf','http://watermark02.silverchair.com/ng_2026_oi.pdf','https://watermark02.silverchair.com.evil.test/ng_2026_oi.pdf']:
            self.assertFalse(native_save.same_pdf_target(source,actual))
        self.assertFalse(native_save.same_pdf_target(source.replace('/articlepdf/','/fullarticle/'),'https://watermark02.silverchair.com/ng_2026_oi.pdf'))

    def test_unknown_access_waits_without_repeating_http_then_oa_can_save(self):
        state={'record':{'title':'Paper','doi':'10.1234/a'},'pdf_links':['https://onlinelibrary.wiley.com/doi/pdf/10.1234/a']}
        current=json.dumps({'url':'https://doi.org/10.1234/a','doi':'10.1234/a'})
        with access.scope('free-only'),patch.object(br,'read_js',side_effect=[current,'false',current,'false']),patch.object(br,'wait_ready'),patch.object(publisher,'direct_pdf',return_value=False) as direct,patch.object(br,'run_js') as click:
            for _ in range(2):
                with self.assertRaises(BrowserError) as error:publisher.article('https://doi.org/10.1234/a','10.1234/a',self.dest,'paper.pdf',self.cp,state)
                self.assertEqual(error.exception.details['kind'],'access_unknown')
            self.assertEqual(direct.call_count,1); click.assert_not_called()
        file=self.root/'saved.pdf';file.write_bytes(PDF)
        with access.scope('free-only'),patch.object(br,'read_js',side_effect=[current,json.dumps({'access':'free','doi':'10.1234/a','evidence':'Open Access'})]),patch.object(br,'wait_ready'),patch.object(publisher,'direct_pdf') as direct,patch.object(br,'run_js') as click,patch.object(publisher.dw,'wait_download',return_value=file),patch.object(publisher,'finish_download',return_value={'status':'complete'}):
            self.assertEqual(publisher.article('https://doi.org/10.1234/a','10.1234/a',self.dest,'paper.pdf',self.cp,state)['status'],'complete')
            direct.assert_not_called();click.assert_called_once()

    def test_batch_skip_preserves_metadata_and_protocol_failure_is_checkpointed(self):
        manifest=self.root/'manifest.json';br.atomic_json(manifest,{'access_policy':'free-only','rows':[{'pmid':'123','title':'Known title','authors':['Ding']},{'pmid':'456','title':'Next title'}]})
        responses=[subprocess.CompletedProcess([],6,json.dumps({'result':{'status':'skipped'}}),''),subprocess.CompletedProcess([],1,'','traceback')]
        with patch.object(pubmed.subprocess,'run',side_effect=responses):
            code,result=self.call(['batch',manifest,'--source','pubmed','--dest',self.dest])
        self.assertEqual(code,70)
        state=br.read_json(str(manifest)+'.batch-progress.json')
        self.assertEqual(state['rows'][0]['title'],'Known title');self.assertEqual(state['rows'][0]['authors'],['Ding'])
        self.assertEqual(state['records']['456']['code'],70);self.assertEqual(result['summary']['pending'],1)

    def test_bibliography_merges_old_skipped_metadata_and_reports_missing_file(self):
        meta=self.root/'metadata.json';progress=self.root/'progress.json';output=self.root/'out.md'
        br.atomic_json(meta,{'rows':[{'pmid':'123','title':'Known title','authors':['Ding']},{'pmid':'456','title':'Missing file'}]})
        br.atomic_json(progress,{'access_policy':'free-only','requested_pmids':['123','456'],'records':{'123':{'code':6,'status':'skipped'},'456':{'status':'complete','path':str(self.root/'absent.pdf'),'verification':{'content_verified':True}}}})
        result=pubmed.bibliography(meta,output,progress=progress)
        self.assertIn('Known title',output.read_text());self.assertEqual(result['summary']['archived'],0)
        self.assertEqual(result['discrepancies'],[{'pmid':'456','reason':'file_missing'}])
