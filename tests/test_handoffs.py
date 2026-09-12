"""Regressions derived from the macOS external-harness BCI test report."""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from academic_automation import browser, browser_runtime as br, cli, cnki, cnki_batch, cnki_bib, interaction, legacy, publisher, search_resume as sr, download_watch as dw
from academic_automation.doi import normalize
from academic_automation.errors import BrowserError


class HandoffTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, {'ACADEMIC_STATE_DIR':str(self.root/'state'),
            'ACADEMIC_BROWSER_BACKEND':'extension', 'ACADEMIC_BROWSER_SESSION':'handoff',
            'CNKI_DOWNLOADS_DIR':str(self.root)})
        env.start(); self.addCleanup(env.stop)
        self.args = ['download','doi','10.1234/first',str(self.root/'papers')]

    def call(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output): code = cli.main(['--json',*args])
        return code, json.loads(output.getvalue())

    def pause(self, checkpoint=''):
        with patch.object(publisher,'download',side_effect=BrowserError('Cloudflare verification',2,{'checkpoint':str(checkpoint)})):
            code, result = self.call(self.args)
        self.assertEqual(code,2)
        return result['result']['pending']

    def acknowledge(self, pending, decision='retry'):
        return self.call(['browser','resolve','--pending-id',pending['id'],'--decision',decision,'--note','用户已完成验证，请继续' if decision=='retry' else '用户明确跳过这篇'])

    def test_wait_blocks_other_paper_retry_flag_legacy_and_new_process(self):
        pending=self.pause()
        with patch.object(publisher,'download') as download, patch.object(legacy,'navigate') as navigate:
            for args in (self.args, self.args+['--retry'], ['download','doi','10.1234/next',str(self.root/'papers')]):
                code,result=self.call(args)
                self.assertEqual(code,2)
                self.assertTrue(result['result']['wait_for_user'])
                self.assertEqual(result['result']['pending']['id'],pending['id'])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(legacy.main(['navigate','https://example.org/other']),2)
            download.assert_not_called();navigate.assert_not_called()
        p=subprocess.run([sys.executable,str(ROOT/'scripts/academic.py'),'--json','--session','other','search','scholar','Q',str(self.root/'out.json')],capture_output=True,text=True)
        self.assertEqual(p.returncode,2,p.stderr)
        self.assertFalse(json.loads(p.stdout)['result']['may_continue_browser'])
        code,status=self.call(['browser','status'])
        self.assertEqual(code,0);self.assertEqual(status['result']['pending']['id'],pending['id'])

    def test_acknowledgement_only_releases_original_action(self):
        pending=self.pause();self.assertEqual(self.acknowledge(pending)[0],0)
        with patch.object(publisher,'download',return_value={'path':'saved.pdf'}) as download:
            self.assertEqual(self.call(['download','doi','10.1234/next',str(self.root/'papers')])[0],2)
            download.assert_not_called()
            self.assertEqual(self.call(self.args)[0],0)
            self.assertTrue(download.call_args.args[-1])
        self.assertIsNone(interaction.read())

    def test_repeated_challenge_revokes_acknowledgement(self):
        pending=self.pause();self.acknowledge(pending)
        with patch.object(publisher,'download',side_effect=BrowserError('Still verifying',2)):
            self.assertEqual(self.call(self.args)[0],2)
        self.assertFalse(interaction.read()['user_confirmed'])

    def test_skip_needs_current_id_and_reply_and_retains_decision(self):
        pending=self.pause()
        self.assertEqual(self.call(['browser','resolve','--pending-id','wrong','--decision','skip','--note','skip'])[0],64)
        self.assertEqual(self.call(['browser','resolve','--pending-id',pending['id'],'--decision','skip'])[0],64)
        self.assertIsNotNone(interaction.read())
        self.assertEqual(self.acknowledge(pending,'skip')[1]['result']['status'],'skipped_by_user')
        self.assertIsNone(interaction.read())
        decision=json.loads((self.root/'state/user-decisions'/ (pending['id']+'.json')).read_text())
        self.assertEqual(decision['user_decision']['note'],'用户明确跳过这篇')
        with patch.object(publisher,'download') as download:
            code,result=self.call(self.args)
            self.assertEqual(code,6);self.assertEqual(result['status'],'skipped')
            download.assert_not_called()
        self.assertEqual(self.acknowledge(pending)[0],0)
        with patch.object(publisher,'download',return_value={'path':'later.pdf'}):
            self.assertEqual(self.call(self.args)[0],0)

    def test_batch_replay_retains_explicit_skip_and_continues(self):
        dest=self.root/'papers'; listing=self.root/'list.txt'
        listing.write_text('论文|张三|'+str(dest)+'\n论文|张三|'+str(dest)+'\n')
        with patch.object(cnki,'download',side_effect=BrowserError('CAPTCHA',2)):
            code,result=self.call(['download','cnki','论文','张三',str(dest)])
        self.assertEqual(code,2)
        self.acknowledge(result['result']['pending'],'skip')
        with patch.object(cnki_batch.time,'sleep'):
            code,result=self.call(['batch',str(listing)])
        self.assertEqual(code,0,result)
        self.assertEqual(result['result']['downloaded'],0)
        self.assertEqual(result['result']['skipped_by_user'],2)
        self.assertEqual(result['result']['failed'],0)

    def test_saved_manual_file_recovers_without_reply_or_browser(self):
        dest=self.root/'papers';cp=dest/'.academic-downloads/test.json'
        br.atomic_json(cp,{'status':'waiting','downloads':str(self.root),'before':dw.snapshot(self.root),'since':0,'name':'requested.pdf'})
        self.pause(cp)
        (self.root/'browser (1).pdf').write_bytes(b'%PDF-1.4\narticle')
        with patch.object(publisher,'download') as download:
            code,result=self.call(self.args)
        self.assertEqual(code,0,result);download.assert_not_called()
        self.assertTrue((dest/'requested.pdf').exists());self.assertIsNone(interaction.read())

    def test_manual_archive_does_not_clear_unrelated_pending(self):
        cp=self.root/'papers/.academic-downloads/a.json';self.pause(cp)
        with patch.object(cnki,'finish_download') as finish:
            code,_=self.call(['archive',str(self.root/'other'),'--file','f.pdf','--checkpoint',str(self.root/'other/.academic-downloads/b.json')])
            self.assertEqual(code,2);finish.assert_not_called()
        self.assertIsNotNone(interaction.read())

    def test_legacy_oa_preserves_needs_user_code(self):
        with patch.object(publisher,'download',side_effect=BrowserError('Manual save',2)),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(legacy.main(['oa','10.1234/first',str(self.root/'papers')]),2)
        self.assertIsNotNone(interaction.read())

    def test_main_pdf_outranks_and_excludes_appendices(self):
        old='Appendix@@https://www.jmir.org/files/app3.pdf\nPDF@@https://www.jmir.org/2026/1/e92940/PDF'
        self.assertEqual(publisher.pdf_candidates(old),['https://www.jmir.org/2026/1/e92940/PDF'])
        rows=[{'label':'PDF','url':'https://x.org/a.pdf','supplement':True},
              {'label':'PDF','url':'https://x.org/other.pdf'},
              {'label':'Article PDF','url':'https://x.org/main','source':'citation_pdf_url'}]
        self.assertEqual(publisher.pdf_candidates(json.dumps(rows)),['https://x.org/main','https://x.org/other.pdf'])
        self.assertEqual(publisher.pdf_candidates('PDF@@https://x.org/app3.pdf'),[])

    def test_doi_tracking_cleaned_before_longest_selection(self):
        doi='10.53469/JRVE.2025.7(09).12'
        self.assertEqual(normalize('https://doi.org/'+doi+'?utm_source=cnki'),doi)
        self.assertEqual(normalize(doi+'?utm_source=cnki'),doi)
        self.assertEqual(normalize('10.1234/a?b'),'10.1234/a?b')
        source=(ROOT/'scripts/cnki_meta.js').read_text()
        fixture='''const vm=require('vm');const document={title:'Article - 中国知网',body:{innerText:'DOI: DOI_VALUE\\nAuthors: A'},querySelectorAll:()=>[{href:'https://doi.org/DOI_VALUE?utm_source=long-tracker'}]};process.stdout.write(vm.runInNewContext(SOURCE,{document,location:{href:'https://cnki.net/article'}}));'''.replace('DOI_VALUE',doi).replace('SOURCE',json.dumps(source))
        result=subprocess.run(['node','-e',fixture],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout)['doi'],doi)
        self.assertEqual(cnki_bib.doi_link('https://doi.org/'+doi+'?utm_source=cnki'),'https://doi.org/'+doi)

    def test_challenge_and_not_found_probes(self):
        source=(ROOT/'scripts/browser_ready.js').read_text().replace('__OPTIONS__','{"mode":"publisher"}')
        for title,body,expected in [('Just a moment...','Checking your browser','captcha'),('论文','正在进行安全验证','captcha'),('Security verification','AWS WAF','captcha'),('404 Not Found','Not found','not_found'),('An article','Journal is subscription based. '+('Text '*50),None)]:
            fixture='''const vm=require('vm');const document={title:TITLE,body:{innerText:BODY},readyState:'complete',querySelectorAll:()=>[],querySelector:()=>null};process.stdout.write(vm.runInNewContext(SOURCE,{document,location:{href:'https://x.org/article'},window:{innerHeight:900},URL,getComputedStyle:()=>({visibility:'visible'})}));'''.replace('TITLE',json.dumps(title)).replace('BODY',json.dumps(body)).replace('SOURCE',json.dumps(source))
            result=json.loads(subprocess.run(['node','-e',fixture],capture_output=True,text=True,check=True).stdout)
            if expected:self.assertTrue(result[expected],result)
            else:self.assertFalse(result['captcha']);self.assertFalse(result['login'])
        with patch.object(br,'run_js',return_value=json.dumps({'not_found':True,'url':'https://cnki.net/stale'})):
            with self.assertRaises(BrowserError) as error:br.wait_ready('cnki-meta')
        self.assertEqual(error.exception.code,3)

    def test_stale_metadata_preserves_success_and_failing_identity(self):
        urls=self.root/'urls.txt';urls.write_text('https://x.org/one\nhttps://x.org/stale\n')
        out=self.root/'metadata.json'
        args=argparse.Namespace(query=str(urls),output=str(out),meta_script=str(ROOT/'scripts/cnki_meta.js'),refresh=False)
        with patch.object(sr,'navigate'),patch.object(sr,'wait_ready',side_effect=[{},BrowserError('PAGE_NOT_FOUND',3)]),patch.object(sr,'run_js',return_value=json.dumps({'title':'One','authors':'A','url':'https://x.org/one'})),patch.object(sr.time,'sleep'):
            with self.assertRaises(BrowserError) as error:sr.metadata(args)
        self.assertEqual(error.exception.details['failed_url'],'https://x.org/stale')
        self.assertEqual(len(json.loads(out.read_text())),1)
        state=json.loads(Path(str(out)+'.progress.json').read_text())
        self.assertIn('https://x.org/one',state['records']);self.assertIn('https://x.org/stale',state['errors'])

    def test_duplicate_suffix_without_space_and_ambiguous_files(self):
        for name in ('论文_张三(1).pdf','论文_张三 (2).pdf'):(self.root/name).write_bytes(b'%PDF-1.4\narticle')
        self.assertEqual(len(dw.candidates(self.root,{},'张三')),2)
        with self.assertRaises(BrowserError) as error:dw.wait_download(self.root,{},'张三',timeout=.01,interval=.01)
        self.assertEqual(error.exception.code,4)

    def test_cnki_file_timeout_is_pending_not_unavailable(self):
        with patch.dict(os.environ, {'ACADEMIC_BROWSER_BACKEND':'apple-events'}),patch.object(cnki,'locate'),patch.object(br,'run_file',return_value='clicked'),patch.object(dw,'wait_download',side_effect=BrowserError('NOTFOUND',4)):
            with self.assertRaises(BrowserError) as error:cnki._download('论文','张三',self.root/'papers')
        self.assertEqual(error.exception.code,2)
        self.assertTrue(Path(error.exception.details['checkpoint']).exists())

    def test_download_hint_only_for_same_origin(self):
        source=(ROOT/'scripts/pub/jump.js').read_text().replace('__NAME__','"paper.pdf"')
        for url,same in [('https://x.org/PDF',True),('https://cdn.example/PDF',False)]:
            fixture='''const vm=require('vm');let clicked=0;const a={click(){clicked++},remove(){}};const location={href:'https://x.org/article',origin:'https://x.org'};const document={createElement:()=>a,body:{appendChild(){}}};vm.runInNewContext(SOURCE,{URL,location,document});process.stdout.write(JSON.stringify({clicked,url:location.href,name:a.download}));'''.replace('SOURCE',json.dumps(source.replace('__URL__',json.dumps(url))))
            data=json.loads(subprocess.run(['node','-e',fixture],capture_output=True,text=True,check=True).stdout)
            self.assertEqual(data['clicked'],1 if same else 0)
            if same:self.assertEqual(data['name'],'paper.pdf')
            else:self.assertEqual(data['url'],url)


if __name__=='__main__':unittest.main()
