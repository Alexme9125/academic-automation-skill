"""Regressions from the macOS extension trial. No site/account is contacted."""
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
from unittest.mock import patch
from http.client import IncompleteRead

from pdf_fixture import PDF, pdf_bytes
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from academic_automation import browser, browser_runtime as br, cnki, publisher, cli, interaction, pdf_verify, native_save
from academic_automation import download_watch as dw, cnki_batch, download_capture
from academic_automation.errors import BrowserError
from academic_automation.redaction import redact


class Response(io.BytesIO):
    def __init__(self, body=PDF, headers=None, status=200):
        super().__init__(body)
        self.headers = {'Content-Length': str(len(body)), **(headers or {})}
        self.status = status


class ExtensionRepairTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, {'ACADEMIC_STATE_DIR':str(self.root/'state'),
            'CNKI_DOWNLOADS_DIR':str(self.root/'downloads'), 'ACADEMIC_BROWSER_BACKEND':'extension',
            'ACADEMIC_BROWSER_SESSION':'repairs', 'PLAYWRIGHT_MCP_EXTENSION_TOKEN':'fixture-connect-token'})
        env.start(); self.addCleanup(env.stop)
        (self.root/'downloads').mkdir()
        self.dest = self.root/'papers'; self.cp = self.dest/'.academic-downloads/task.json'

    def call(self, args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out): code = cli.main(['--json', *map(str,args)])
        return code, json.loads(out.getvalue())['result']

    def test_cnki_trailer_is_preserved_but_arbitrary_or_cut_data_is_rejected(self):
        trailer=b'WebFastLoad\xef\xbb\xbf<FileProperty><Doi /><FileName>JYCH202626036</FileName><TableName>CJFDTotal</TableName><Type>JOURNAL</Type></FileProperty>'
        for data,expected in [(PDF,True),(PDF+trailer,True),(PDF+trailer[:-3],False),(PDF+b'unexpected garbage',False),(PDF[:-20],False)]:
            path=self.root/'candidate.pdf';path.write_bytes(data)
            self.assertEqual(dw.valid_file(path),expected)

    def test_http_truncation_preserves_diagnostics_and_never_creates_final(self):
        target = self.root/'paper.pdf'
        with patch.object(publisher, 'urlopen', side_effect=lambda *a,**k:Response(PDF[:-30], {'Content-Length':str(len(PDF))})) as get, patch.object(publisher.time, 'sleep'):
            self.assertFalse(publisher.direct_pdf('https://x.test/paper.pdf', target))
        self.assertEqual(get.call_count, 2); self.assertFalse(target.exists())
        attempts = br.read_json(str(target)+'.http.json')
        self.assertEqual([r['error'] for r in attempts], ['incomplete_transfer']*2)
        self.assertTrue(all(Path(r['part']).exists() for r in attempts))

    def test_http_bounded_retry_can_produce_a_complete_real_pdf(self):
        target = self.root/'paper.pdf'
        with patch.object(publisher, 'urlopen', side_effect=[Response(PDF[:-30], {'Content-Length':str(len(PDF))}), Response()]), patch.object(publisher.time, 'sleep'):
            self.assertTrue(publisher.direct_pdf('https://x.test/paper.pdf', target))
        self.assertEqual(target.read_bytes(), PDF)
        self.assertEqual(br.read_json(str(target)+'.http.json')[-1]['received_bytes'],len(PDF))

    def test_partial_or_encoded_responses_are_not_full_pdfs(self):
        for headers,status in [({'Content-Range':'bytes 0-100/200'},206), ({'Content-Encoding':'gzip'},200)]:
            target = self.root/(str(status)+'.pdf')
            with patch.object(publisher,'urlopen',return_value=Response(headers=headers,status=status)) as get:
                self.assertFalse(publisher.direct_pdf('https://x.test/paper.pdf',target))
            self.assertEqual(get.call_count,1); self.assertFalse(target.exists())

    def test_unknown_length_requires_pdf_structure_even_without_pypdf(self):
        for data,expected in [(PDF,True),(PDF[:-8],False),(b'<html>fake</html>',False)]:
            target=self.root/('candidate'+str(len(data))+'.pdf')
            response=Response(data); response.headers={}
            with patch.object(publisher,'urlopen',return_value=response), patch.object(pdf_verify,'available',return_value=False):
                self.assertEqual(publisher.direct_pdf('https://x.test/pdf',target),expected)

    def test_chunked_disconnect_never_promotes_a_part(self):
        def response(*a,**k):
            r=Response(); r.read=lambda size: (_ for _ in ()).throw(IncompleteRead(b'partial'))
            return r
        with patch.object(publisher,'urlopen',side_effect=response) as get, patch.object(publisher.time,'sleep'):
            self.assertFalse(publisher.direct_pdf('https://x.test/pdf',self.root/'p.pdf'))
        self.assertEqual(get.call_count,2);self.assertFalse((self.root/'p.pdf').exists())

    def test_parse_failure_is_different_from_missing_or_unextractable_text(self):
        path=self.root/'bad.pdf';path.write_bytes(b'%PDF-1.4\nnot a document\nstartxref\n9\n%%EOF')
        with patch.object(pdf_verify,'available',return_value=True):
            with self.assertRaises(BrowserError) as error:pdf_verify.verify(path,{})
        self.assertEqual(error.exception.details['verification']['status'],'invalid')
        with patch.object(pdf_verify,'available',return_value=False):
            self.assertEqual(pdf_verify.verify(path,{})['reason'],'pypdf_not_installed')
        with patch.dict(sys.modules, {'pypdf': types.SimpleNamespace(PdfReader=unittest.mock.Mock())}), patch.object(pdf_verify,'available',return_value=True):
            reader = sys.modules['pypdf'].PdfReader
            reader.return_value.pages=[unittest.mock.Mock()]
            reader.return_value.pages[0].extract_text.side_effect=ValueError('font')
            self.assertEqual(pdf_verify.verify(path,{})['reason'],'text_extraction_failed')

    def test_old_corrupt_cache_pauses_then_acknowledged_retry_keeps_evidence(self):
        self.dest.mkdir(); path=self.dest/'old.pdf'; path.write_bytes(PDF[:-20]); stat=path.stat()
        state={'status':'complete','file':{'path':str(path),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns},
               'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        br.atomic_json(self.cp,state)
        args=['download','doi','10.1234/a',self.dest,'--access-policy','all']
        with patch.object(publisher,'pending_path',return_value=self.cp), patch.object(publisher,'resolve_doi') as resolve:
            code,result=self.call(args)
            self.assertEqual(code,2); self.assertEqual(result['kind'],'invalid_file');resolve.assert_not_called()
            self.assertEqual(self.call(args+['--retry'])[0],2);resolve.assert_not_called()
            self.call(['browser','resolve','--pending-id',result['pending']['id'],'--decision','retry','--note','Test user: retry the damaged download'])
            with patch.object(publisher,'article',return_value={'status':'complete'}):
                self.assertEqual(self.call(args)[0],0)
            resolve.assert_called_once()
        self.assertTrue(path.exists());self.assertEqual(br.read_json(self.cp)['rejected_files'][0]['path'],str(path))

    def test_normal_file_cache_verifies_body_without_redownloading(self):
        p=self.root/'good.pdf';p.write_bytes(pdf_bytes('Matching title and Author Smith. '+ 'Abstract '*10))
        result=cnki.finish_download(p,self.dest,self.cp,{'record':{'title':'Matching title','first_author':'Author Smith'}})
        self.assertEqual(result['verification']['content_verified'],pdf_verify.available())
        self.assertTrue(cnki.resume_download(self.cp,self.dest)['cached'])
        self.assertEqual(len(list(self.dest.glob('*.pdf'))),1)

    def test_cnki_retry_does_not_readopt_previously_rejected_named_file(self):
        self.dest.mkdir(); old=self.dest/'title_author.pdf';old.write_bytes(PDF)
        br.atomic_json(self.cp,{'status':'retry_ready','rejected_files':[{'path':str(old)}]})
        fresh=self.root/'fresh.pdf';fresh.write_bytes(PDF)
        with patch.object(cnki,'pending_path',return_value=self.cp), patch.object(cnki_batch,'existing_exact',return_value=old), patch.object(cnki,'locate') as locate, patch.object(cnki,'extension_download',return_value=fresh):
            result=cnki._download('title','author',self.dest,retry=True)
        locate.assert_called_once();self.assertNotEqual(result['path'],str(old))
        self.assertEqual(result['rejected_files'][0]['path'],str(old));self.assertTrue(old.exists())

    def test_pubmed_retry_keeps_rejected_named_file_and_reaches_download(self):
        self.dest.mkdir(); old=self.dest/'PMID-31647093.pdf';old.write_bytes(PDF[:-20])
        br.atomic_json(self.cp,{'status':'retry_ready','phase':'publisher',
            'rejected_files':[{'path':str(old)}],
            'record':{'href':'https://pubmed.ncbi.nlm.nih.gov/31647093/', 'doi':'10.1093/hmg/ddz204',
                      'full_text_links':[{'url':'https://x.test/article','access':'free'}]}})
        with patch.object(cnki,'pending_path',return_value=self.cp), patch.object(publisher,'article',return_value={'status':'complete'}) as article:
            code,result=self.call(['download','pubmed','31647093',self.dest,'--access-policy','all'])
        self.assertEqual(code,0,result);article.assert_called_once();self.assertTrue(old.exists())

    def test_internal_connection_page_and_failed_script_are_rejected_and_redacted(self):
        transport=browser.ExtensionBrowser()
        for page in [dict(url='chrome-extension://abc/connect.html?token=secret',title='Welcome',script_url='chrome-extension://abc/connect.html?token=secret'),
                     dict(url='https://x.test',title='X',script_url='https://other.test')]:
            with patch.object(browser,'cli_call'), patch.object(transport,'_code',return_value=page):
                with self.assertRaises(BrowserError) as error:transport.connect()
            self.assertNotIn('token=secret',str(error.exception.details));self.assertFalse(browser.read_session())

    def test_token_gate_precedes_attach_and_preserves_existing_connection(self):
        browser.save_session({'connected':True,'page':{'url':'https://x.test'}})
        before=browser.session_path().read_bytes()
        for token in ('',' \n '):
            with patch.dict(os.environ,{'PLAYWRIGHT_MCP_EXTENSION_TOKEN':token}), patch.object(browser,'cli_call') as attach:
                code,result=self.call(['browser','connect','--url','https://x.test'])
            self.assertEqual(code,2);self.assertEqual(result['kind'],'extension_token')
            self.assertTrue(result['wait_for_user']);self.assertFalse(result['may_continue_browser'])
            attach.assert_not_called();self.assertEqual(browser.session_path().read_bytes(),before)

    def test_token_gate_allows_supplied_value_without_recording_it(self):
        page={'url':'https://x.test','title':'X','script_url':'https://x.test'}
        with patch.object(browser,'cli_call') as attach, patch.object(browser.ExtensionBrowser,'_code',return_value=page):
            code,result=self.call(['browser','connect'])
        self.assertEqual(code,0,result);attach.assert_called_once()
        token=os.environ['PLAYWRIGHT_MCP_EXTENSION_TOKEN']
        self.assertNotIn(token,json.dumps(result));self.assertNotIn(token,browser.session_path().read_text())
        self.assertNotIn(token,str(attach.call_args))

    def test_existing_session_and_api_doctor_do_not_require_token_again(self):
        browser.save_session({'connected':True})
        with patch.dict(os.environ,{'PLAYWRIGHT_MCP_EXTENSION_TOKEN':''}), patch.object(browser.ExtensionBrowser,'_code',return_value='ready'):
            self.assertEqual(browser.ExtensionBrowser().code('async page => true'),'ready')
            code,result=self.call(['doctor','--capability','pubmed-data'])
        self.assertEqual(code,0,result)
        self.assertFalse(result['capabilities']['browser']['extension_token']['present'])

    def test_explicit_new_tab_and_script_probe_are_required_before_connected(self):
        page=dict(url='https://x.test',title='X',script_url='https://x.test')
        with patch.object(browser,'cli_call') as call, patch.object(browser.ExtensionBrowser,'_code',return_value=page):
            result=browser.ExtensionBrowser().connect('https://x.test')
        self.assertTrue(result['connected']);self.assertEqual(call.call_args_list[1].args,('tab-new','https://x.test'))
        with self.assertRaises(BrowserError):browser.ExtensionBrowser().connect('file:///tmp/private')

    def test_secret_filter_covers_persisted_nested_diagnostics(self):
        with patch.dict(os.environ,{'PLAYWRIGHT_MCP_EXTENSION_TOKEN':'fixture-secret'}):
            br.atomic_json(self.root/'diagnostic.json',{'text':'failure fixture-secret','page':{'url':'chrome-extension://abc/connect.html?token=old-secret&port=1'}})
        data=(self.root/'diagnostic.json').read_text()
        self.assertNotIn('fixture-secret',data);self.assertNotIn('old-secret',data)
        self.assertEqual(redact('https://publisher.test/pdf?signed=needed'),'https://publisher.test/pdf?signed=needed')

    def test_pdf_resume_does_not_resolve_doi_reopen_article_or_reclick(self):
        state={'publisher_stage':'pdf_requested','url':'https://x.test/main.pdf','status':'waiting'}
        p=self.root/'saved.pdf';p.write_bytes(PDF)
        with patch.object(browser.ExtensionBrowser,'select_pdf_popup'), patch.object(br,'read_js',return_value='{"url":"https://x.test/main.pdf","type":"application/pdf"}'), patch.object(br,'navigate') as nav, patch.object(publisher,'direct_pdf') as direct, patch.object(native_save,'save_pdf',return_value=p):
            self.assertEqual(publisher._article('https://x.test/article','10.1234/a',self.dest,'a.pdf',self.cp,state,False,[])['status'],'complete')
        nav.assert_not_called();direct.assert_not_called()
        br.atomic_json(self.cp,{'status':'waiting','publisher_stage':'pdf_requested','url':'https://x.test/main.pdf'})
        with patch.object(publisher,'pending_path',return_value=self.cp), patch.object(publisher,'resolve_doi') as resolve, patch.object(publisher,'resume_publisher_pdf',return_value={'status':'complete'}) as resume:
            self.assertEqual(publisher._download('10.1234/a',self.dest,retry=True)['status'],'complete')
        resolve.assert_not_called();resume.assert_called_once()

    def test_pdf_verification_or_wrong_pdf_never_starts_native_save(self):
        for typ,url in [('text/html','https://x.test/main.pdf'),('application/pdf','https://x.test/another.pdf')]:
            state={'publisher_stage':'pdf_requested','url':'https://x.test/main.pdf','status':'waiting'}
            with patch.object(browser.ExtensionBrowser,'select_pdf_popup'), patch.object(br,'read_js',return_value=json.dumps({'url':url,'type':typ})), patch.object(br,'wait_ready',side_effect=BrowserError('CAPTCHA',2)), patch.object(native_save,'save_pdf') as save, patch.object(br,'navigate') as nav:
                with self.assertRaises(BrowserError):publisher.resume_publisher_pdf(self.dest,'a.pdf',self.cp,state)
            save.assert_not_called();nav.assert_not_called()

    def test_extension_native_bridge_rejects_other_window_url(self):
        with patch.object(browser.platform,'system',return_value='Darwin'), patch.object(browser.ExtensionBrowser,'code',return_value={'url':'https://x.test/a.pdf','type':'application/pdf'}), patch.object(browser,'run_process',return_value='{"window":1,"tab":2,"url":"https://x.test/other.pdf"}'):
            with self.assertRaises(BrowserError):browser.ExtensionBrowser().native_binding()

    def test_native_window_matches_observed_tab_group_without_ignoring_identity(self):
        fixture='''const h=require(SCRIPT),bounds={x:1,y:33,width:1728,height:997};
const base={name:'ddz204.pdf - Google Chrome',role:'AXWindow',subrole:'AXStandardWindow',geometry:[1,33,1728,997]};
const rows=[base,{...base,name:'ddz204.pdf - Part of group Playwright · playwright-cli - Google Chrome'},
{...base,name:'another.pdf - Part of group Playwright - Google Chrome'},
{...base,geometry:[400,33,1728,997]},{...base,subrole:'AXDialog'},
{...base,name:'ddz204.pdf - arbitrary suffix - Google Chrome'}];
process.stdout.write(JSON.stringify(rows.map(r=>h.matchesNativeWindow('ddz204.pdf',bounds,r))));'''.replace('SCRIPT',json.dumps(str(ROOT/'scripts/macos_pdf_save.js')))
        result=json.loads(subprocess.run(['node','-e',fixture],capture_output=True,text=True,check=True).stdout)
        self.assertEqual(result,[True,True,False,False,False,False])

    def test_detached_pdf_recovery_from_connection_page_is_unique_and_target_checked(self):
        target='https://academic.oup.com/hmg/article-pdf/28/R2/R170/31081074/ddz204.pdf'
        actual='https://watermark02.silverchair.com/ddz204.pdf?fixture=1'
        transport=browser.ExtensionBrowser()
        def pages(source):
            fixture='''const vm=require('vm');
const current={url:()=>CURRENT};
const pdf={url:()=>ACTUAL,opener:async()=>null};
current.context=()=>({pages:()=>[current,pdf]});
(async()=>process.stdout.write(JSON.stringify(await vm.runInNewContext('('+SOURCE+')',{})(current))))();'''
            fixture=fixture.replace('CURRENT',json.dumps('chrome-extension://fixture/connect.html')).replace('ACTUAL',json.dumps(actual)).replace('SOURCE',json.dumps(source))
            return json.loads(subprocess.run(['node','-e',fixture],capture_output=True,text=True,check=True).stdout)
        with patch.object(transport,'code',side_effect=lambda s: actual if s=='async page => page.url()' else pages(s)), patch.object(browser,'cli_call') as select:
            transport.select_pdf_popup(target)
        select.assert_called_once_with('tab-select','1')
        for rows,selected in [([{'index':1,'url':actual,'current':False}]*2,actual),
                              ([{'index':1,'url':actual,'current':False}],'https://x.test/unrelated.pdf')]:
            with patch.object(transport,'code',side_effect=[rows,selected]), patch.object(browser,'cli_call'):
                with self.assertRaises(BrowserError):transport.select_pdf_popup(target)

    def test_cookie_and_background_preflight_have_zero_clicks(self):
        source=(ROOT/'scripts/cnki_download_action.js').read_text().replace('__SELECTOR__','"#pdf"').replace('__CAPTURE__','"capture.part"').replace('__EVENT_TIMEOUT__','10').replace('__PROBE__','"probe"')
        for flags,expected in [({'visibility':'visible','consent':True},'needs_consent'),({'visibility':'hidden'},'needs_foreground'),({'visibility':'visible','captcha':True},'needs_verification')]:
            fixture='''const vm=require('vm');let clicks=0,front=0;
const page={bringToFront:async()=>front++,evaluate:async()=>JSON.stringify(FLAGS),url:()=> 'https://x.test/article',locator:()=>({click:async()=>clicks++})};
(async()=>{const result=await vm.runInNewContext('('+SOURCE+')',{})(page);process.stdout.write(JSON.stringify({result,clicks,front}))})().catch(e=>{console.error(e);process.exit(1)});'''.replace('FLAGS',json.dumps(flags)).replace('SOURCE',json.dumps(source))
            result=json.loads(subprocess.run(['node','-e',fixture],capture_output=True,text=True,check=True).stdout)
            self.assertEqual(result['clicks'],0);self.assertEqual(result['front'],1);self.assertEqual(result['result']['status'],expected)

    def test_context_popup_download_is_captured_once_and_unrelated_page_is_ignored(self):
        source=(ROOT/'scripts/cnki_download_action.js').read_text().replace('__SELECTOR__','"#pdf"').replace('__CAPTURE__','"capture.part"').replace('__EVENT_TIMEOUT__','10').replace('__PROBE__','"probe"')
        fixture='''const vm=require('vm');let clicks=0,saves=0;const events={},main={};
const ctx={on(e,f){events[e]=f},off(){}};
const page={bringToFront:async()=>{},evaluate:async()=>JSON.stringify({visibility:'visible'}),url:()=> 'https://x/article',context:()=>ctx,
on(e,f){main[e]=f},off(){},waitForTimeout:()=>new Promise(r=>setTimeout(r,20)),
locator:()=>({async click(o){if(o.trial)return;clicks++;
const spawn=opener=>{const listeners={};const p={opener:async()=>opener,on(e,f){listeners[e]=f},off(){},url:()=> 'https://x/pdf'};
events.page(p);listeners.download({suggestedFilename:()=> 'a.pdf',url:()=> 'https://x/pdf',saveAs:async()=>saves++});};
spawn(null);spawn(page);}})};
(async()=>{const result=await vm.runInNewContext('('+SOURCE+')',{})(page);process.stdout.write(JSON.stringify({result,clicks,saves}))})().catch(e=>{console.error(e);process.exit(1)});'''.replace('SOURCE',json.dumps(source))
        result=json.loads(subprocess.run(['node','-e',fixture],capture_output=True,text=True,check=True).stdout)
        self.assertEqual(result['clicks'],1);self.assertEqual(result['saves'],1)
        self.assertEqual(len(result['result']['observed']),1);self.assertTrue(result['result']['saved'])

    def test_legacy_pdf_handoff_migrates_stage_without_reading_browser(self):
        br.atomic_json(self.cp,{'status':'waiting','publisher_url':'https://x/article','url':'https://x/a.pdf'})
        with patch.object(br,'navigate') as navigate:
            self.assertIsNone(cnki.resume_download(self.cp,self.dest,retry=True))
        self.assertEqual(br.read_json(self.cp)['publisher_stage'],'pdf_requested');navigate.assert_not_called()

    def test_corrupt_cached_file_can_be_replaced_by_explicit_manual_archive(self):
        self.dest.mkdir();old=self.dest/'a.pdf';old.write_bytes(PDF[:-10])
        br.atomic_json(self.cp,{'status':'complete','verification':{'status':'invalid'},'name':'a.pdf'})
        source=self.root/'manual.pdf';source.write_bytes(PDF)
        code,result=self.call(['archive',self.dest,'--file',source,'--checkpoint',self.cp])
        self.assertEqual(code,0,result);self.assertNotEqual(result['path'],str(old));self.assertTrue(old.exists())

    def test_failed_trial_does_not_claim_a_download_was_clicked(self):
        source=(ROOT/'scripts/cnki_download_action.js').read_text().replace('__SELECTOR__','"#pdf"').replace('__CAPTURE__','"capture.part"').replace('__EVENT_TIMEOUT__','10').replace('__PROBE__','"probe"')
        fixture='''const vm=require('vm');let clicks=0;
const page={bringToFront:async()=>{},evaluate:async()=>JSON.stringify({visibility:'visible'}),url:()=> 'https://x.test/article',locator:()=>({click:async o=>{if(o.trial)throw Error('overlay');clicks++}})};
(async()=>{const result=await vm.runInNewContext('('+SOURCE+')',{})(page);process.stdout.write(JSON.stringify({result,clicks}))})().catch(e=>{console.error(e);process.exit(1)});'''.replace('SOURCE',json.dumps(source))
        result=json.loads(subprocess.run(['node','-e',fixture],capture_output=True,text=True,check=True).stdout)
        self.assertEqual(result['clicks'],0);self.assertFalse(result['result']['click_attempted'])


if __name__=='__main__':unittest.main()
