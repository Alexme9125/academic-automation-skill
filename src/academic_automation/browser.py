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
from pathlib import Path

from .errors import BrowserError
from .paths import ROOT, state_dir


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
        cli_call('attach', '--extension=chrome', timeout=120)
        save_session({'connected': True})
        return {'backend': 'extension', 'session': session_name(), 'connected': True}

    def disconnect(self):
        cli_call('detach')
        session_path().unlink(missing_ok=True)
        return {'connected': False}

    def code(self, source):
        if not read_session().get('connected'):
            raise BrowserError('NEED_CONNECTION: run browser connect and select a Chrome tab', 2)
        # A file avoids Windows command length/quoting limits and keeps extracted data
        # out of the shell. The source is trusted repository JavaScript.
        with tempfile.TemporaryDirectory(prefix='academic-js-') as tmp:
            path = Path(tmp) / 'operation.js'
            path.write_text(source, encoding='utf-8')
            return cli_result(cli_call('run-code', '--filename=' + str(path)))

    def evaluate(self, js):
        value = self.code('async page => { return await page.evaluate(' + json.dumps(js) + '); }')
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

    def navigate(self, url):
        self.code('async page => { await page.goto(' + json.dumps(url) +
                  ', {waitUntil:"domcontentloaded", timeout:30000}); return page.url(); }')


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
        return self.target('''try
execute t javascript "window.stop()"
end try
set URL of t to (item 1 of argv)
return "navigated"''', url)


def get_browser():
    name = backend_name()
    if name == 'apple-events':
        return AppleEventsBrowser()
    if name == 'extension':
        return ExtensionBrowser()
    raise BrowserError('Unknown browser backend: ' + name, 64)
