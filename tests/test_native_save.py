"""Offline native-save contracts; these do not claim macOS UI acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pdf_fixture import PDF, pdf_bytes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from academic_automation import access, browser, browser_runtime as br, cnki, native_save, publisher
from academic_automation.errors import BrowserError


class NativeSaveTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.cp = self.root / 'task.json'
        self.state = {'status': 'waiting', 'name': 'article.pdf'}
        env = patch.dict(os.environ, {'ACADEMIC_STATE_DIR': str(self.root / 'state'),
            'ACADEMIC_BROWSER_BACKEND': 'apple-events', 'CNKI_DOWNLOADS_DIR': str(self.root)})
        env.start(); self.addCleanup(env.stop)
        browser.save_session({'window': 10, 'tab': 20})
        probe = patch.object(br, 'read_js', return_value='{"url":"https://example.org/a.pdf","type":"application/pdf"}')
        probe.start(); self.addCleanup(probe.stop)

    def js(self, body):
        source = 'const m = require(' + json.dumps(str(ROOT / 'scripts/macos_pdf_save.js')) + ');\n' + body
        return subprocess.run(['node', '-e', source], capture_output=True, text=True, check=True)

    def test_viewer_button_ignores_drive_and_browser_downloads(self):
        self.js('''const assert=require('assert');
const context=['sidenavToggle','pageSelector','print'].map(id=>({id}));
const drive={role:'AXButton',id:'save',description:'Save to Google Drive',enabled:true};
const download={role:'AXButton',id:'save',description:'Download',enabled:true};
const checkbox={role:'AXCheckBox',description:'Downloads',enabled:true};
assert.strictEqual(m.downloadButton([...context,drive,checkbox,download]),download);
for(const label of ['下载','下載']) assert.strictEqual(m.downloadButton([...context,{...download,description:label}]).description,label);
for(const rows of [[...context,drive,checkbox],[download],[...context,download,{...download}],
                  [...context,{...download,enabled:false}]]) assert.throws(()=>m.downloadButton(rows));''')

    def test_save_sheet_rejects_replace_wrong_path_and_tags(self):
        self.js('''const assert=require('assert');
const rows=[{role:'AXTextField',name:'Save As:',value:'received.pdf'},
 {role:'AXTextField',name:'Tags:',value:''},{role:'AXPopUpButton',name:'Where:',value:'unique-folder'},
 {role:'AXButton',name:'Save',enabled:true},{role:'AXButton',name:'Cancel',enabled:true}];
const c=m.saveControls(rows); m.checkDestination(c,'received.pdf','unique-folder');
for(const labels of [{'Save As:':'存储为：','Where:':'位置：','Save':'存储','Cancel':'取消'},
                     {'Save As:':'儲存為：','Where:':'位置：','Save':'儲存','Cancel':'取消'}]) {
 m.checkDestination(m.saveControls(rows.map(r=>({...r,name:labels[r.name]||r.name}))), 'received.pdf','unique-folder');
}
assert.throws(()=>m.checkDestination(c,'other.pdf','unique-folder'));
assert.throws(()=>m.checkDestination(c,'received.pdf','Downloads'));
assert.throws(()=>m.saveControls(rows.filter(r=>r.name!=='Save As:')));
assert.throws(()=>m.saveControls(rows.map(r=>r.name==='Save'?{...r,name:'Replace'}:r)));
assert.throws(()=>m.saveControls([...rows,rows[0]]));''')

    def test_windows_never_invokes_native_runtime(self):
        with patch.object(browser, 'run_process') as run:
            with patch.object(native_save.platform, 'system', return_value='Windows'):
                self.assertIsNone(native_save.save_pdf(self.cp, self.state, 'https://example.org/a.pdf'))
            run.assert_not_called()
        self.assertFalse(self.cp.exists())

    def test_attempt_is_journaled_before_click_and_timeout_is_never_replayed(self):
        def fail(*args, **kwargs):
            self.assertEqual(br.read_json(self.cp)['native_save']['status'], 'attempted')
            raise BrowserError('operation may have completed', 70)
        with patch.object(native_save.platform, 'system', return_value='Darwin'), patch.object(browser, 'run_process', side_effect=fail) as run, patch.object(native_save, 'recovered_file', return_value=None):
            for _ in range(2):
                with self.assertRaises(BrowserError) as error:
                    native_save.save_pdf(self.cp, self.state, 'https://example.org/a.pdf')
                self.assertEqual(error.exception.code, 2)
            self.assertEqual(run.call_count, 1)
        self.assertEqual(br.read_json(self.cp)['native_save']['phase'], 'unknown')

    def test_success_requires_real_stable_file_and_retains_event_evidence(self):
        def save(args, **kwargs):
            request = br.read_json(args[-1])
            Path(request['folder'], request['filename']).write_bytes(PDF)
            return json.dumps({'status': 'dialog_closed', 'events': ['download_clicked', 'save_clicked', 'dialog_closed']})
        with patch.object(native_save.platform, 'system', return_value='Darwin'), patch.object(browser, 'run_process', side_effect=save), patch.object(br, 'read_js', return_value='{"url":"https://watermark02.silverchair.com/ddz204.pdf?token=private","type":"application/pdf"}'):
            path = native_save.save_pdf(self.cp, self.state, 'https://academic.oup.com/hmg/article-pdf/28/R2/R170/31081074/ddz204.pdf')
        self.assertTrue(path.is_file())
        self.assertEqual(self.state['native_save']['status'], 'file_verified')
        self.assertIn('save_clicked', self.state['native_save']['events'])
        self.assertNotIn('token=private', self.cp.read_text())
        self.assertFalse((path.parent / 'request.json').exists())

    def test_redirect_requires_observed_publisher_host_and_same_pdf_filename(self):
        source = 'https://academic.oup.com/hmg/article-pdf/28/R2/R170/31081074/ddz204.pdf'
        self.assertTrue(native_save.same_pdf_target(source, source + '#page=2'))
        self.assertTrue(native_save.same_pdf_target(source, 'https://watermark02.silverchair.com/ddz204.pdf?token=opaque'))
        for actual in ['https://watermark02.silverchair.com/other.pdf', 'https://unrelated.example/ddz204.pdf',
                       'http://watermark02.silverchair.com/ddz204.pdf', 'https://watermark02.silverchair.com.evil.example/ddz204.pdf']:
            self.assertFalse(native_save.same_pdf_target(source, actual))
        with patch.object(native_save.platform, 'system', return_value='Darwin'), patch.object(browser, 'run_process') as run:
            with self.assertRaises(BrowserError): native_save.save_pdf(self.cp, self.state, source)
            run.assert_not_called()

    def test_dialog_closed_without_file_is_not_success(self):
        with patch.object(native_save.platform, 'system', return_value='Darwin'), patch.object(browser, 'run_process', return_value='{"status":"dialog_closed"}'), patch.object(native_save, 'recovered_file', return_value=None):
            with self.assertRaises(BrowserError) as error:
                native_save.save_pdf(self.cp, self.state, 'https://example.org/a.pdf')
        self.assertEqual(error.exception.code, 2)

    def test_permission_denial_is_a_checkpointed_handoff(self):
        with patch.object(native_save.platform, 'system', return_value='Darwin'), patch.object(browser, 'run_process', return_value='{"status":"needs_user","phase":"preflight","error":"Not authorized to send Apple events"}'), patch.object(native_save, 'recovered_file', return_value=None):
            with self.assertRaises(BrowserError) as error:
                native_save.save_pdf(self.cp, self.state, 'https://example.org/a.pdf')
        self.assertEqual(error.exception.code, 2)
        self.assertIn('Accessibility', str(error.exception))
        self.assertEqual(error.exception.details['checkpoint'], str(self.cp))

    def test_native_file_is_recovered_before_request_and_archived_without_overwrite(self):
        staging = self.root / 'staging'; staging.mkdir()
        candidate = staging / 'received.pdf'; candidate.write_bytes(PDF)
        self.state['native_save'] = {'folder': str(staging), 'filename': 'received.pdf', 'since': 0, 'status': 'attempted'}
        br.atomic_json(self.cp, self.state)
        dest = self.root / 'papers'; dest.mkdir()
        (dest / 'article.pdf').write_bytes(pdf_bytes('original'))
        with patch.object(browser, 'run_process') as run:
            result = cnki.resume_download(self.cp, dest, retry=True)
            cached = cnki.resume_download(self.cp, dest)
            run.assert_not_called()
        self.assertEqual(Path(result['path']).name, 'article (1).pdf')
        self.assertTrue(cached['cached']); self.assertFalse(candidate.exists())
        self.assertIn(b'original', (dest / 'article.pdf').read_bytes())

    def test_partial_or_html_native_file_cannot_recover(self):
        staging = self.root / 'staging'; staging.mkdir()
        candidate = staging / 'received.pdf'
        self.state['native_save'] = {'folder': str(staging), 'filename': candidate.name, 'since': 0}
        candidate.write_bytes(b'<html>challenge</html>')
        self.assertIsNone(native_save.recovered_file(self.state, timeout=.6))
        candidate.write_bytes(b'%PDF-1.4\nstill writing')
        candidate.with_suffix('.pdf.crdownload').write_bytes(b'partial')
        self.assertIsNone(native_save.recovered_file(self.state, timeout=.6))

    def test_retry_cannot_reclick_unresolved_native_save(self):
        self.state['native_save'] = {'folder': str(self.root / 'missing'), 'filename': 'received.pdf', 'since': 0}
        br.atomic_json(self.cp, self.state)
        with self.assertRaises(BrowserError) as error:
            cnki.resume_download(self.cp, self.root / 'papers', retry=True)
        self.assertEqual(error.exception.code, 2)

    def test_only_known_preflight_failure_allows_acknowledged_native_retry(self):
        self.state['native_save'] = {'folder': str(self.root / 'missing'), 'filename': 'received.pdf',
            'since': 0, 'url': 'https://example.org/a.pdf', 'status': 'needs_user', 'phase': 'preflight', 'events': []}
        br.atomic_json(self.cp, self.state)
        with patch.object(native_save, 'save_pdf', return_value=None) as save:
            with self.assertRaises(BrowserError): cnki.resume_download(self.cp, self.root / 'papers', retry=False)
            save.assert_not_called()
            with self.assertRaises(BrowserError): cnki.resume_download(self.cp, self.root / 'papers', retry=True)
            self.assertEqual(save.call_count, 1)
            self.assertTrue(save.call_args.kwargs['retry_preflight'])
        for phase, events in [('unknown', []), ('download_clicked', ['download_clicked']), ('preflight', None)]:
            self.state['native_save'].update(phase=phase, events=events)
            self.assertFalse(native_save.can_retry_preflight(self.state))

    def test_native_preflight_rejects_wrong_window_tab_url_html_or_existing_dialog(self):
        # Execute the actual JXA entry point with native objects replaced by
        # read-only fixtures; no write/click API exists in this preflight fixture.
        self.js('''const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(require.resolve(''' + json.dumps(str(ROOT / 'scripts/macos_pdf_save.js')) + '''),'utf8');
for(const changed of ['window','tab','url','ax','dialog','html']) {
 const request={window:10,tab:20,url:'https://x/a.pdf'};
 const tab={id:()=>changed==='tab'?21:20,url:()=>changed==='url'?'https://x/b.pdf':request.url};
 const win={id:()=>changed==='window'?11:10,activeTab:()=>tab,name:()=> 'a.pdf',bounds:()=>({x:1,y:33,width:1728,height:997})};
 const ax={name:()=>changed==='ax'?'Other window':'a.pdf - Google Chrome',sheets:()=>changed==='dialog'?[{}]:[],
   role:()=> 'AXWindow',subrole:()=> 'AXStandardWindow',position:()=>[1,33],size:()=>[1728,997]};
 const process={windows:()=>[ax]},chrome={running:()=>true,windows:()=>[win],execute:()=>changed==='html'?'text/html':'application/pdf'};
 const ctx={ObjC:{import(){},unwrap:x=>x},$:{NSString:{stringWithContentsOfFileEncodingError:()=>JSON.stringify(request)}},
 Application:name=>name==='Google Chrome'?chrome:{processes:{byName:()=>process}}};
 vm.createContext(ctx);vm.runInContext(source,ctx);const r=JSON.parse(ctx.run(['request.json']));
 assert.strictEqual(r.status,'needs_user');assert.strictEqual(r.phase,'preflight');assert.deepStrictEqual(r.events,[]);
 assert(!r.error.includes('not a function'),r.error);
}''')

    def test_native_recovery_keeps_pubmed_identity_check(self):
        from academic_automation import pdf_verify
        candidate = self.root / 'received.pdf'; candidate.write_bytes(PDF)
        self.state.update(source='pubmed', record={'title': 'Expected paper'}, native_save={'folder': str(self.root), 'filename': candidate.name, 'since': 0})
        br.atomic_json(self.cp, self.state)
        with patch.object(pdf_verify, 'verify', side_effect=BrowserError('PDF_IDENTITY_MISMATCH', 2)):
            with self.assertRaises(BrowserError): cnki.resume_download(self.cp, self.root / 'papers')
        self.assertTrue(candidate.exists()); self.assertFalse((self.root / 'papers').exists())

    def test_publisher_only_attempts_native_after_mac_no_file_not_captcha(self):
        url = 'https://example.org/a.pdf'
        saved = self.root / 'received.pdf'; saved.write_bytes(PDF)
        for backend, code, expected in [('apple-events', 4, True), ('apple-events', 2, False), ('apple-events', 70, False), ('extension', 4, True)]:
            state = {'status': 'waiting', 'record': {'title': 'fixture'}}
            with access.scope('all'), patch.object(browser, 'backend_name', return_value=backend), patch.object(br, 'read_js', side_effect=['{"url":"https://example.org/article"}', '{"url":"https://example.org/a.pdf","type":"application/pdf"}']), patch.object(browser.ExtensionBrowser, 'select_pdf_popup'), patch.object(br, 'wait_ready'), patch.object(br, 'run_js'), patch.object(publisher, 'direct_pdf', return_value=False), patch('academic_automation.download_capture.capture', return_value=None), patch('academic_automation.download_capture.publisher_control', return_value='#pdf'), patch.object(native_save.dw, 'wait_download', side_effect=BrowserError('fixture', code)), patch.object(native_save, 'save_pdf', return_value=saved) as native, patch.object(publisher, 'finish_download', return_value={'status': 'complete'}):
                if expected:
                    self.assertEqual(publisher._article('https://example.org/article', '', self.root, '', self.cp, state, False, [url])['status'], 'complete')
                else:
                    with self.assertRaises(BrowserError): publisher._article('https://example.org/article', '', self.root, '', self.cp, state, False, [url])
                self.assertEqual(native.called, expected)


if __name__ == '__main__': unittest.main()
