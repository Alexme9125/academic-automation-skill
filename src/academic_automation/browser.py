"""Browser transports. Only the extension transport needs Node.js."""
import contextlib
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urldefrag

from .errors import BrowserError
from .paths import ROOT, SCRIPTS, state_dir


def backend_name():
    override = os.environ.get('ACADEMIC_BROWSER_BACKEND')
    if override:
        return override
    package = ROOT / 'platform.json'
    if package.is_file():
        return json.loads(package.read_text(encoding='utf-8'))['default_backend']
    return 'apple-events' if platform.system() == 'Darwin' else 'extension'


def session_name():
    name = os.environ.get('ACADEMIC_BROWSER_SESSION', 'academic')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', name):
        raise BrowserError('Session must contain 1–64 letters, numbers, underscores or hyphens', 64)
    return name


@contextlib.contextmanager
def browser_lock():
    folder = state_dir()
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'browser.lock').open('a+b') as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise BrowserError('BROWSER_BUSY: another academic task is using this browser', 75) from exc
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def session_path():
    # Playwright CLI sessions are scoped to cwd. Keep connection metadata scoped
    # to that same installed skill, while the operation lock remains user-wide.
    workspace = hashlib.sha256(str(ROOT).encode('utf-8')).hexdigest()[:12]
    return state_dir() / (backend_name() + '-' + session_name() + '-' + workspace + '.json')


def read_session():
    try:
        return json.loads(session_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_session(data):
    from .browser_runtime import atomic_json
    atomic_json(session_path(), data)


def run_process(cmd, timeout=30):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=timeout, cwd=str(ROOT))
    except FileNotFoundError as exc:
        raise BrowserError('MISSING_RUNTIME: ' + str(cmd[0]), 69) from exc
    except subprocess.TimeoutExpired as exc:
        raise BrowserError('BROWSER_TIMEOUT: operation may have completed; inspect before retrying', 70) from exc
    if result.returncode:
        raise BrowserError((result.stderr or result.stdout).strip() or 'Browser command failed', 70)
    return result.stdout.strip()


def cli_command():
    node = shutil.which('node')
    entry = ROOT / 'node_modules' / '@playwright' / 'cli' / 'playwright-cli.js'
    if not node or not entry.is_file():
        raise BrowserError('MISSING_RUNTIME: install Node.js, then run npm ci --ignore-scripts in the skill directory', 69)
    expected = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['dependencies']['@playwright/cli']
    installed = json.loads(entry.with_name('package.json').read_text(encoding='utf-8'))['version']
    if installed != expected:
        raise BrowserError('RUNTIME_VERSION_MISMATCH: run npm ci --ignore-scripts in the skill directory', 69)
    # Invoke Node directly: .cmd shims and cmd.exe quoting break on Windows paths.
    return [node, str(entry), '-s=' + session_name()]


def cli_call(*args, timeout=45):
    output = run_process(cli_command() + list(args), timeout)
    if re.search(r'^### Error\b', output, re.M):
        raise BrowserError(output, 70)
    return output


def cli_result(output):
    match = re.search(r'^### Result\s*\n', output, re.M)
    if not match:
        raise BrowserError('BROWSER_PROTOCOL: missing JSON result from pinned Playwright CLI', 70)
    try:
        result, _ = json.JSONDecoder().raw_decode(output[match.end():].lstrip())
        return result
    except ValueError as exc:
        raise BrowserError('BROWSER_PROTOCOL: invalid JSON result', 70) from exc


class ExtensionBrowser:
    def connect(self):
        # The extension presents the browser/tab selection UI. No cookie export.
        session_path().unlink(missing_ok=True)
        try:
            cli_call('attach', '--extension=chrome', timeout=120)
            page = self._code('async page => ({url:page.url(), title:await page.title()})')
            if not isinstance(page, dict) or not page.get('url'):
                raise BrowserError('Selected tab could not be read', 70)
        except BrowserError as exc:
            if exc.code == 69:
                raise
            raise BrowserError('NEED_CONNECTION: attach was not verified; select a Chrome tab and run browser connect again', 2,
                               {'phase': 'connect_probe', 'cause': str(exc)}) from exc
        save_session({'connected': True, 'verified_at': time.time(), 'page': page})
        return {'backend': 'extension', 'session': session_name(), 'connected': True, 'page': page}

    def disconnect(self):
        cli_call('detach')
        session_path().unlink(missing_ok=True)
        return {'connected': False}

    def code(self, source, timeout=45):
        if not read_session().get('connected'):
            raise BrowserError('NEED_CONNECTION: run browser connect and select a Chrome tab', 2)
        try:
            return self._code(source, timeout)
        except BrowserError as exc:
            if re.search(r"browser.*(?:is not open|not connected)|session.*not found", str(exc), re.I):
                session_path().unlink(missing_ok=True)
                raise BrowserError('NEED_CONNECTION: the Playwright session is no longer available; reconnect the existing Chrome', 2,
                                   {'cause': str(exc)}) from exc
            raise

    def _code(self, source, timeout=45):
        # A file avoids Windows command length/quoting limits and keeps extracted data
        # out of the shell. The source is trusted repository JavaScript.
        with tempfile.TemporaryDirectory(prefix='academic-js-') as tmp:
            path = Path(tmp) / 'operation.js'
            path.write_text(source, encoding='utf-8')
            # Keep the established default call shape for the compatibility layer.
            args = ('run-code', '--filename=' + str(path))
            return cli_result(cli_call(*args, **({'timeout': timeout} if timeout != 45 else {})))

    def evaluate(self, js):
        value = self.code('async page => { return await page.evaluate(' + json.dumps(js) + '); }')
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

    def navigate(self, url):
        # Readiness is checked by the caller. Waiting for commit avoids unrelated
        # slow deferred scripts blocking an already usable CNKI document.
        marker = uuid.uuid4().hex
        return self.code('''async page => {
          const token = TOKEN, target = TARGET;
          await page.evaluate(t => { window.__academicNavigationToken = t; }, token);
          try {
            await page.goto(target, {waitUntil:"commit", timeout:30000});
            return {url:page.url(), committed:true};
          } catch (e) {
            if (e.name !== 'TimeoutError') throw e;
            const fresh = await page.evaluate(t => window.__academicNavigationToken !== t
              && document.readyState !== 'loading', token).catch(() => false);
            if (!fresh) throw e;
            return {url:page.url(), committed:true, recovered_timeout:true};
          }
        }'''.replace('TOKEN', json.dumps(marker)).replace('TARGET', json.dumps(url)))

    def cnki_download(self, selector, capture_path, event_timeout=12000):
        source = (SCRIPTS / 'cnki_download_action.js').read_text(encoding='utf-8')
        values = {'__SELECTOR__': selector, '__CAPTURE__': str(capture_path), '__EVENT_TIMEOUT__': event_timeout}
        source = re.sub(r'__SELECTOR__|__CAPTURE__|__EVENT_TIMEOUT__', lambda m: json.dumps(values[m[0]]), source)
        return self.code(source, timeout=90)


class AppleEventsBrowser:
    def call(self, script, *args):
        if platform.system() != 'Darwin':
            raise BrowserError('Apple Events requires macOS; select --backend extension', 69)
        try:
            return run_process(['osascript', '-e', script, *args])
        except BrowserError as exc:
            if 'JavaScript through AppleScript is turned off' in str(exc) or 'JavaScript from Apple Events' in str(exc):
                raise BrowserError('APPLE_EVENTS_DISABLED: enable Chrome > View > Developer > Allow JavaScript from Apple Events', 2) from exc
            if 'connected tab was closed' in str(exc):
                raise BrowserError('NEED_CONNECTION: the selected Chrome tab was closed; run browser connect again', 2) from exc
            raise

    def connect(self):
        ids = self.call('''tell application "Google Chrome"
activate
if (count of windows) = 0 then make new window
return (id of front window as text) & ":" & (id of active tab of front window as text)
end tell''')
        window, tab = map(int, ids.split(':'))
        save_session({'window': window, 'tab': tab})
        return {'backend': 'apple-events', 'window': window, 'tab': tab, 'connected': True}

    def disconnect(self):
        session_path().unlink(missing_ok=True)
        return {'connected': False}

    def target(self, action, argument):
        data = read_session()
        if not data:
            self.connect(); data = read_session()
        script = '''on run argv
tell application "Google Chrome"
repeat with w in windows
if (id of w as text) = "WINDOW_ID" then
repeat with t in tabs of w
if (id of t as text) = "TAB_ID" then
ACTION
end if
end repeat
end if
end repeat
error "The connected tab was closed. Run browser connect again."
end tell
end run'''.replace('WINDOW_ID', str(int(data['window']))).replace('TAB_ID', str(int(data['tab']))).replace('ACTION', action)
        return self.call(script, argument)

    def evaluate(self, js):
        return self.target('return execute t javascript (item 1 of argv)', js)

    def navigate(self, url):
        token = json.dumps(uuid.uuid4().hex)
        old_url = self.evaluate('(function(){window.__academicNavigationToken=' + token + ';return location.href;})()')
        self.target('''try
execute t javascript "window.stop()"
end try
set URL of t to (item 1 of argv)
return "navigated"''', url)
        if old_url != url and urldefrag(old_url)[0] == urldefrag(url)[0]:
            return 'navigated'
        # Chrome accepts set URL before replacing the current document. A marker
        # distinguishes the old page even when it is complete or has the same URL,
        # while allowing institution proxies to redirect to a different hostname.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            committed = self.evaluate('String(window.__academicNavigationToken !== ' + token +
                                      ' && document.readyState !== "loading")')
            if committed == 'true':
                return 'navigated'
            time.sleep(.25)
        raise BrowserError('NAVIGATION_TIMEOUT: Chrome has not loaded a new document', 70)


def get_browser():
    name = backend_name()
    if name == 'apple-events':
        return AppleEventsBrowser()
    if name == 'extension':
        return ExtensionBrowser()
    raise BrowserError('Unknown browser backend: ' + name, 64)
