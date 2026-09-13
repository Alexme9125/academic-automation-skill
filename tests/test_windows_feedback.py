"""Windows report regressions. Offline fixtures do not claim Windows acceptance."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pdf_fixture import PDF

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from academic_automation import browser, browser_runtime as br, cli, cnki, cnki_batch, interaction, publisher, download_watch as dw
from academic_automation.errors import BrowserError


class WindowsFeedbackTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, {'ACADEMIC_STATE_DIR':str(self.root/'state'),
            'CNKI_DOWNLOADS_DIR':str(self.root), 'ACADEMIC_BROWSER_BACKEND':'extension',
            'ACADEMIC_BROWSER_SESSION':'windows-feedback'})
        env.start(); self.addCleanup(env.stop)
        self.args = ['download','cnki','论文','张三',str(self.root/'papers')]

    def call(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output): code = cli.main(['--json',*args])
        return code, json.loads(output.getvalue())

    def selected(self):
        return json.dumps({'status':'selected','kind':'pdf','selector':'#pdfDown',
                           'href':'javascript:void(0)','url':'https://example.org/article'})

    def test_direct_workflow_calls_rejected_before_side_effects(self):
        with patch.object(cnki,'locate') as locate, patch.object(publisher,'resolve_doi') as resolve, patch.object(cnki,'start_chinese') as search:
            calls = [lambda:cnki.download('论文','张三',self.root/'out'),
                     lambda:publisher.download('10.1234/test',self.root/'out'),
                     lambda:cnki.chinese_search('主题',self.root/'out.json'),
                     lambda:cnki.foreign_search('topic',self.root/'out.json')]
            for call in calls:
                with self.assertRaises(BrowserError) as error: call()
                self.assertEqual(error.exception.code,64)
            locate.assert_not_called(); resolve.assert_not_called(); search.assert_not_called()
        self.assertFalse((self.root/'out').exists())

    def test_acknowledged_timeout_keeps_original_task_and_blocks_other_tasks(self):
        with patch.object(cnki,'download',side_effect=BrowserError('Login required',2)):
            code,result=self.call(self.args)
        pending=result['result']['pending']
        self.assertEqual(code,2)
        self.call(['browser','resolve','--pending-id',pending['id'],'--decision','retry','--note','Fixture user replied'])
        with patch.object(cnki,'download',side_effect=BrowserError('WAIT_TIMEOUT cnki-meta',70,{'retryable':True})):
            code,result=self.call(self.args)
        self.assertEqual(code,70)
        self.assertEqual(result['result']['pending']['id'],pending['id'])
        with patch.object(cnki,'download') as download:
            self.assertEqual(self.call(['download','cnki','另一篇','李四',str(self.root/'papers')])[0],2)
            download.assert_not_called()

    def test_readiness_timeout_is_transient(self):
        with self.assertRaises(BrowserError) as error:br.wait_ready('cnki-meta',timeout=0)
        self.assertEqual(error.exception.code,70)
        self.assertTrue(error.exception.details['retryable'])

    def test_navigation_timeout_accepts_only_a_new_document(self):
        for fresh in (True,False):
            sources=[]
            with patch.object(browser.ExtensionBrowser,'code',side_effect=lambda source:sources.append(source)):
                browser.ExtensionBrowser().navigate('https://x.example/article')
            fixture='''const vm=require('vm');let calls=0,until='';
const page={evaluate:async()=>++calls===1?undefined:FRESH,url:()=> 'https://x.example/article',
goto:async(url,options)=>{until=options.waitUntil;const e=new Error('late');e.name='TimeoutError';throw e}};
(async()=>{let result,error='';try{result=await vm.runInNewContext('('+SOURCE+')',{})(page)}catch(e){error=e.name}
process.stdout.write(JSON.stringify({result,error,until}))})().catch(e=>{console.error(e);process.exit(1)});'''.replace('FRESH',json.dumps(fresh)).replace('SOURCE',json.dumps(sources[0]))
            r=subprocess.run(['node','-e',fixture],capture_output=True,text=True,check=True)
            result=json.loads(r.stdout)
            self.assertEqual(result['until'],'commit')
            if fresh:self.assertTrue(result['result']['recovered_timeout'])
            else:self.assertEqual(result['error'],'TimeoutError')

    def test_read_only_context_retry_is_bounded_and_writes_are_not_replayed(self):
        failure=BrowserError('Execution context was destroyed',70)
        with patch.object(br,'run_js',side_effect=[failure,'ready']) as run, patch.object(br.time,'sleep'):
            self.assertEqual(br.read_js('document.title'),'ready'); self.assertEqual(run.call_count,2)
        with patch.object(br,'run_js',side_effect=failure) as run, patch.object(br.time,'sleep'):
            with self.assertRaises(BrowserError):br.read_js('document.title')
            self.assertEqual(run.call_count,3)
        with patch.object(br,'get_browser') as get:
            get.return_value.evaluate.side_effect=failure
            with self.assertRaises(BrowserError):br.run_js('button.click()')
            self.assertEqual(get.return_value.evaluate.call_count,1)

    def test_connect_probes_before_publishing_session_and_invalidates_stale_session(self):
        transport=browser.ExtensionBrowser()
        browser.save_session({'connected':True})
        with patch.object(browser,'cli_call',return_value='attached'), patch.object(transport,'_code',side_effect=BrowserError("browser 'academic' is not open",70)):
            with self.assertRaises(BrowserError) as error:transport.connect()
        self.assertEqual(error.exception.code,2); self.assertFalse(browser.read_session())
        with patch.object(browser,'cli_call',return_value='attached'), patch.object(transport,'_code',return_value={'title':'CNKI','url':'https://cnki.net','script_url':'https://cnki.net'}):
            result=transport.connect()
        self.assertTrue(result['connected']);self.assertIn('verified_at',browser.read_session())
        with patch.object(transport,'_code',side_effect=BrowserError("The browser 'academic' is not open",70)):
            with self.assertRaises(BrowserError) as error:transport.code('async page => true')
        self.assertEqual(error.exception.code,2);self.assertFalse(browser.read_session())

    def test_event_capture_preserves_author_checks_and_avoids_second_click(self):
        def capture(selector,path):
            Path(path).write_bytes(PDF)
            return {'saved':True,'suggested_filename':'论文_张三.pdf','status':'download_event'}
        with patch.object(cnki,'locate'),patch.object(cnki,'page_status',return_value='detail'),patch.object(br,'read_js',return_value=self.selected()),patch.object(browser.ExtensionBrowser,'cnki_download',side_effect=capture) as click:
            code,result=self.call(self.args)
            self.assertEqual(code,0,result)
            self.assertTrue(dw.valid_file(result['result']['path']))
            self.assertEqual(self.call(self.args)[0],0)
            self.assertEqual(click.call_count,1)
        state=br.read_json(result['result']['checkpoint'])
        self.assertTrue(state['download_event']['saved'])
        self.assertEqual(state['download_control']['href'],'javascript:void(0)')

    def test_captured_wrong_author_pauses_instead_of_archiving(self):
        def capture(selector,path):
            Path(path).write_bytes(PDF)
            return {'saved':True,'suggested_filename':'其他文章_李四.pdf'}
        with patch.object(cnki,'locate'),patch.object(cnki,'page_status',return_value='detail'),patch.object(br,'read_js',return_value=self.selected()),patch.object(browser.ExtensionBrowser,'cnki_download',side_effect=capture):
            code,result=self.call(self.args)
        self.assertEqual(code,2);self.assertIsNotNone(interaction.read())
        self.assertFalse(list((self.root/'papers').glob('*.pdf')))

    def test_no_event_checks_browser_saved_file_without_reclicking(self):
        saved=self.root/'论文_张三.pdf';saved.write_bytes(PDF)
        with patch.object(cnki,'locate'),patch.object(cnki,'page_status',return_value='detail'),patch.object(br,'read_js',return_value=self.selected()),patch.object(browser.ExtensionBrowser,'cnki_download',return_value={'status':'no_event'}) as click,patch.object(dw,'wait_download',return_value=saved):
            code,result=self.call(self.args)
        self.assertEqual(code,0,result);self.assertEqual(click.call_count,1)

    def test_no_event_and_no_file_pause_then_manual_file_recovers(self):
        with patch.object(cnki,'locate'),patch.object(cnki,'page_status',return_value='detail'),patch.object(br,'read_js',return_value=self.selected()),patch.object(browser.ExtensionBrowser,'cnki_download',return_value={'status':'no_event'}) as click,patch.object(dw,'wait_download',side_effect=BrowserError('no file',4)):
            code,result=self.call(self.args)
            self.assertEqual(code,2);self.assertTrue(result['result']['wait_for_user'])
            self.assertEqual(self.call(self.args+['--retry'])[0],2)
            self.assertEqual(click.call_count,1)
        saved=self.root/'论文_张三.pdf';saved.write_bytes(PDF)
        with patch.object(dw,'wait_download',return_value=saved),patch.object(browser.ExtensionBrowser,'cnki_download') as click:
            self.assertEqual(self.call(self.args)[0],0);click.assert_not_called()
        self.assertIsNone(interaction.read())

    def test_partial_transport_file_blocks_retry_until_manually_resolved(self):
        cp=cnki.pending_path(self.root/'papers',cnki_batch.identity('论文','张三',self.root/'papers'))
        part=self.root/'received.part';part.write_bytes(b'%PDF-1.4\npartial')
        br.atomic_json(cp,{'status':'waiting','transfer_file':str(part)})
        with self.assertRaises(BrowserError) as error:cnki.resume_download(cp,self.root/'papers','张三',retry=True)
        self.assertEqual(error.exception.code,2)

    def test_chinese_search_public_cli_saves_partial_and_resumes(self):
        output=self.root/'results.json'
        args=['search','cnki','主题',str(output),'--pages','2']
        def read(name):
            if name=='cnki_count.js':return '{"n":3}'
            return json.dumps({'rows':[{'title':'论文','href':'https://example.org/1'}]})
        with patch.object(cnki,'start_chinese'),patch.object(br,'read_file',side_effect=read),patch.object(br,'run_file',return_value='next'),patch.object(br,'wait_ready',side_effect=[{'signature':'first'},BrowserError('redirect wait',70)]):
            code,result=self.call(args)
        self.assertEqual(code,70);self.assertFalse(br.read_json(output)['complete'])
        self.assertEqual(len(br.read_json(str(output)+'.progress.json')['pages']),1)
        with patch.object(cnki,'start_chinese'),patch.object(br,'read_file',side_effect=read),patch.object(br,'run_file',return_value='next'),patch.object(br,'wait_ready',return_value={'signature':'ready'}),patch.object(cnki.time,'sleep'):
            code,result=self.call(args)
        self.assertEqual(code,0,result);self.assertEqual(result['result']['n'],1)
        with patch.object(cnki,'start_chinese') as start:
            self.assertEqual(self.call(args)[0],0);start.assert_not_called()

    def test_chinese_search_handoff_blocks_download_queue(self):
        with patch.object(cnki,'start_chinese',side_effect=BrowserError('Login',2)):
            code,result=self.call(['search','cnki',"SU='近视'",str(self.root/'out.json'),'--expert'])
        self.assertEqual(code,2);self.assertIn('pending',result['result'])
        with patch.object(cnki,'download') as download:
            self.assertEqual(self.call(self.args)[0],2);download.assert_not_called()

    def test_batch_stops_on_uncertain_transport_error(self):
        listing=self.root/'list.txt';listing.write_text('甲|张三|'+str(self.root/'papers')+'\n乙|李四|'+str(self.root/'papers'))
        with patch.object(sys,'argv',['batch',str(listing)]),patch.object(cnki_batch.subprocess,'run',return_value=subprocess.CompletedProcess([],70,'context destroyed')) as run:
            with self.assertRaises(SystemExit) as error:cnki_batch.main()
        self.assertEqual(error.exception.code,70);self.assertEqual(run.call_count,1)

    def test_locator_action_clicks_once_even_if_click_reports_error_after_download(self):
        source=(ROOT/'scripts/cnki_download_action.js').read_text().replace('__SELECTOR__','"#pdfDown"').replace('__CAPTURE__','"capture.part"').replace('__EVENT_TIMEOUT__','10').replace('__PROBE__', '"probe"')
        fixture='''const vm=require('vm');let clicks=0,saves=0,removed=0;const listeners={};
const page={bringToFront:async()=>{},evaluate:async()=>JSON.stringify({visibility:'visible'}),context:()=>({on(){},off(){}}),on(e,f){listeners[e]=f},off(e,f){removed++},url(){return 'https://x/article'},waitForTimeout(){return Promise.resolve()},
locator(){return {async click(options){if(options.trial)return;clicks++;listeners.download({suggestedFilename:()=> '论文_张三.pdf',url:()=> 'https://x/file',async saveAs(){saves++}});throw new Error('Execution context was destroyed')}}}};
(async()=>{const result=await vm.runInNewContext('('+SOURCE+')',{page})(page);process.stdout.write(JSON.stringify({result,clicks,saves,removed}))})().catch(e=>{console.error(e);process.exit(1)});'''.replace('SOURCE',json.dumps(source))
        r=subprocess.run(['node','-e',fixture],capture_output=True,text=True,check=True)
        result=json.loads(r.stdout)
        self.assertEqual(result['clicks'],1);self.assertEqual(result['saves'],1)
        self.assertTrue(result['result']['saved']);self.assertEqual(result['removed'],2)


if __name__=='__main__':unittest.main()
