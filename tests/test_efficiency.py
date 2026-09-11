"""Offline behavior checks. No browser, network, or user downloads are touched."""
import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import browser_runtime as br
import download_watch as dw
import cnki_batch as batch
import cnki_index as index
import search_resume as sr


class Clock:
    def __init__(self): self.value = 0
    def now(self): return self.value
    def sleep(self, seconds): self.value += seconds


class EfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def pdf(self, name, folder=None):
        p = (folder or self.d) / name
        p.write_bytes(b'%PDF-1.4\n1 0 obj <</Type /Pages /Count 1>> endobj\n%%EOF')
        return p

    def test_unrelated_partial_does_not_block(self):
        old = self.pdf('old_张三.pdf')
        before = dw.snapshot(self.d)
        (self.d / 'huge.zip.crdownload').write_bytes(b'pending')
        expected = self.pdf('new_张三.pdf')
        self.assertEqual(dw.wait_download(self.d, before, '张三', timeout=1, interval=.01), expected)
        self.assertTrue(old.exists())

    def test_own_partial_and_ambiguous_downloads_rejected(self):
        self.pdf('new_张三.pdf')
        (self.d / 'new_张三.pdf.crdownload').write_bytes(b'pending')
        self.assertFalse(dw.candidates(self.d, {}, '张三'))
        self.pdf('a.pdf'); self.pdf('b.pdf')
        with self.assertRaises(br.BrowserError):
            dw.wait_download(self.d, {}, timeout=.03, interval=.01)

    def test_html_disguised_as_pdf_and_appledouble_ignored(self):
        (self.d/'bad.pdf').write_text('<html>access denied</html>')
        self.pdf('._copy.pdf')
        self.assertEqual(dw.candidates(self.d, {}), [])

    def test_delayed_fee_and_captcha_interrupt_file_wait(self):
        for kind, code in [('fee', 5), ('captcha', 2)]:
            c = Clock()
            with patch.object(dw, 'run_file', side_effect=['order', kind]), patch.object(dw.time, 'monotonic', c.now), patch.object(dw.time, 'sleep', c.sleep):
                with self.assertRaises(br.BrowserError) as e:
                    dw.wait_download(self.d, {}, '张三', timeout=40, page=True)
                self.assertEqual(e.exception.code, code)
                self.assertLess(c.value, 40)

    def test_archive_preserves_existing_file(self):
        dest = self.d/'archive'; dest.mkdir()
        original = self.pdf('paper.pdf', dest)
        source = self.pdf('paper.pdf')
        saved = dw.archive(source, dest)
        self.assertNotEqual(saved, original)
        self.assertTrue(original.exists()); self.assertTrue(saved.exists())
        self.assertFalse(source.exists())

    def test_readiness_waits_for_stability_and_new_page(self):
        c = Clock()
        states = [{'ready': True, 'signature': s, 'url':'test'} for s in ['old','new1','new2','new2','new2']]
        with patch.object(br, 'run_js', side_effect=[json.dumps(x) for x in states]), patch.object(br.time, 'monotonic', c.now), patch.object(br.time, 'sleep', c.sleep):
            result = br.wait_ready('scholar', previous='old')
        self.assertEqual(result['signature'], 'new2')
        self.assertEqual(c.value, 2)

    def test_missing_author_stops_before_browser(self):
        result = subprocess.run(['zsh', str(br.DIR/'cnki_dl.sh'), '超过六个字的长文献标题', '', str(self.d)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 64)
        self.assertIn('NEED_AUTHOR', result.stdout)
        listing = self.d/'list.txt'; listing.write_text('文献甲|作者|'+str(self.d)+'\n文献乙||'+str(self.d))
        with patch.object(sys, 'argv', ['cnki_batch.py', str(listing)]), patch.object(batch.subprocess, 'run') as run:
            with self.assertRaises(SystemExit) as e: batch.main()
            self.assertEqual(e.exception.code, 64); run.assert_not_called()

    def test_identity_survives_reordering_and_file_change_invalidates(self):
        key = batch.identity('题名：《测试》', '张三', str(self.d))
        self.assertEqual(key, batch.identity('题名测试', '张三', str(self.d)))
        p = self.pdf('题名测试_张三.pdf')
        record = batch.file_record(p)
        self.assertTrue(batch.verified(record))
        p.write_bytes(p.read_bytes()+b'changed')
        self.assertFalse(batch.verified(record))
        p.unlink(); self.assertFalse(batch.verified(record))

    def test_expert_index_exact_author_and_ambiguity(self):
        row = lambda title, author, url: {'title':title, 'text':author, 'href':url}
        pages = [[row('测试题名应用策略','张三','u1'), row('测试题名应用','李四','u2')], [row('测试题名应用','张三','u3')]]
        self.assertEqual(index.select(pages,'测试题名应用','张三')['href'], 'u3')
        pages.append([row('测试题名应用','张三','u4')])
        self.assertIsNone(index.select(pages,'测试题名应用','张三'))

    def test_index_detail_uses_article_title_not_hidden_login_heading(self):
        def evaluate(source):
            js='''const vm=require('vm');
const document={title:'测试题名 - 中国知网',body:{innerText:'张三'},querySelector:s=>s==='h1'?{textContent:'自动登录'}:s==='.author'?{textContent:'张三'}:null};
process.stdout.write(vm.runInNewContext(SOURCE,{document}));'''.replace('SOURCE',json.dumps(source))
            return subprocess.run(['node','-e',js],check=True,capture_output=True,text=True).stdout
        with patch.object(index,'wait_ready'), patch.object(index,'run_js',side_effect=evaluate):
            self.assertTrue(index.verify_detail('测试题名','张三'))
            self.assertFalse(index.verify_detail('其他题名','张三'))
            self.assertFalse(index.verify_detail('测试题名','李四'))

    def test_index_expiry_query_and_page_limit(self):
        p=self.d/'index.json'
        br.atomic_json(p,{'query':'Q','limit':3,'created':100,'complete':True,'pages':[]})
        with patch.object(index.time,'time',return_value=101):
            self.assertIsNotNone(index.load_index(p,'Q',3))
            self.assertIsNone(index.load_index(p,'different',3))
            self.assertIsNone(index.load_index(p,'Q',2))
        with patch.object(index.time,'time',return_value=100+86401):
            self.assertIsNone(index.load_index(p,'Q',3))

    def test_partial_search_resumes_without_repeating_completed_page(self):
        out = self.d/'gs.json'
        args = argparse.Namespace(mode='scholar', query='education', output=str(out), pages=2, year='', oa=False, refresh=False)
        first = {'n':1,'rows':[{'title':'A','href':'https://example.org/a'}], 'url':'https://scholar.google.com/scholar?q=education', 'next':'https://scholar.google.com/scholar?q=education&start=10'}
        with patch.object(sr, 'navigate'), patch.object(sr, 'wait_ready', side_effect=[{},br.BrowserError('captcha',2)]), patch.object(sr, 'run_file', return_value=json.dumps(first)), patch.object(sr.time, 'sleep'):
            with self.assertRaises(br.BrowserError): sr.search(args)
        self.assertEqual(br.read_json(out)['n'],1)
        self.assertFalse(br.read_json(out)['complete'])
        second = {'n':1,'rows':[{'title':'B','href':'https://example.org/b'}], 'next':''}
        with patch.object(sr,'navigate') as nav, patch.object(sr,'wait_ready'), patch.object(sr,'run_file',return_value=json.dumps(second)), patch.object(sr.time,'sleep'):
            sr.search(args)
            nav.assert_called_once_with(first['next'])
        self.assertEqual(br.read_json(out)['n'],2)
        self.assertTrue(br.read_json(out)['complete'])

    def test_meta_deduplicates_and_resumes(self):
        urls = self.d/'urls.txt'; urls.write_text('https://example.org/a\nhttps://example.org/a\n')
        args = argparse.Namespace(query=str(urls),output=str(self.d/'meta.json'),refresh=False,meta_script=str(br.DIR/'cnki_meta.js'))
        obj = {'title':'A','doi':'10.1234/test','url':'https://example.org/a'}
        with patch.object(sr,'navigate') as nav, patch.object(sr,'wait_ready'), patch.object(sr,'run_js',return_value=json.dumps(obj)), patch.object(sr.time,'sleep'):
            sr.metadata(args); sr.metadata(args)
            nav.assert_called_once()
        self.assertEqual(len(br.read_json(args.output)),1)

    def test_wos_collect_accumulates_recycled_cards(self):
        cards=[{'href':'u1','title':'A'},{'href':'u2','title':'B'}]
        snapshots=[{'rows':[cards[0]],'n':1},{'rows':[cards[1]],'n':1}]+[{'rows':[cards[1]],'n':1}]*2
        def run(name):
            return json.dumps(snapshots.pop(0)) if name=='wos_rows.js' else '{}'
        with patch.object(sr,'run_file',side_effect=run), patch.object(sr,'run_js',return_value=json.dumps({'slots':2,'bottom':True,'listBottom':True})), patch.object(sr.time,'sleep'):
            data=sr.collect_wos()
        self.assertEqual(data['n'],2)

    def test_hidden_cnki_captcha_template_is_not_a_challenge(self):
        template=(br.DIR/'browser_ready.js').read_text().replace('__OPTIONS__', json.dumps({'mode':'cnki-form','url':''}))
        for top, expected in [(5000,False),(100,True)]:
            js='''const vm=require('vm');
const el={textContent:'拖动下方拼图完成验证',getClientRects:()=>[{}],getBoundingClientRect:()=>({width:300,top:TOP})};
const context={location:{href:'https://kns.cnki.net/test'},window:{innerHeight:900},
  getComputedStyle:()=>({visibility:'visible'}),URL:URL,
  document:{title:'检索-中国知网',body:{innerText:'结果\\n拖动下方拼图完成验证'},readyState:'complete',
  querySelector:()=>({}),querySelectorAll:(s)=>s==='*'?[el]:[]}};
process.stdout.write(vm.runInNewContext(SOURCE,context));
'''.replace('TOP',str(top)).replace('SOURCE',json.dumps(template))
            r=subprocess.run(['node','-e',js],capture_output=True,text=True,check=True)
            self.assertEqual(json.loads(r.stdout)['captcha'],expected)

    def test_batch_duplicate_reorder_and_changed_file(self):
        listing=self.d/'list.txt'; dest=self.d/'archive'; dest.mkdir()
        dl=self.d/'downloads'; dl.mkdir()
        a='文献甲|张三|'+str(dest); b='文献乙|李四|'+str(dest)
        def fake(cmd, **kwargs):
            title,author,folder=cmd[-3:]
            saved=self.pdf(title+'_'+author+'.pdf',Path(folder))
            return subprocess.CompletedProcess(cmd,0,'ARCHIVED: '+str(saved)+'\n')
        with patch.dict(os.environ,{'CNKI_DOWNLOADS_DIR':str(dl)}), patch.object(batch.subprocess,'run',side_effect=fake) as run, patch.object(batch.time,'sleep'), patch.object(sys,'argv',['batch',str(listing)]), contextlib.redirect_stdout(io.StringIO()):
            listing.write_text(a+'\n'+a+'\n'+b+'\n'); batch.main()
            self.assertEqual(run.call_count,2)
            listing.write_text(b+'\n'+a+'\n'); batch.main()
            self.assertEqual(run.call_count,2)
            p=dest/'文献甲_张三.pdf'; p.write_bytes(p.read_bytes()+b'changed')
            batch.main()
            self.assertEqual(run.call_count,3)


if __name__ == '__main__':
    unittest.main()
