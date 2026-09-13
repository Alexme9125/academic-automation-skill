#!/usr/bin/env python3
"""Build reproducible, source-only platform assets without credentials or caches."""
import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ('SKILL.md', 'README.md', 'README.zh-CN.md', 'LICENSE', 'AGENTS.md',
              'VERIFICATION.md', 'RELEASE_NOTES.md', 'package.json', 'package-lock.json', 'requirements-pdf.txt')


def source_files(root, target):
    files = [root / name for name in ROOT_FILES]
    for folder, suffixes in [('src/academic_automation', {'.py'}),
                             ('scripts', {'.py', '.js', '.sh'}),
                             ('references', {'.md'}), ('tests', {'.py', '.html', '.js'})]:
        for path in (root / folder).rglob('*'):
            if '__pycache__' in path.parts or not path.is_file() or path.suffix not in suffixes:
                continue
            if target == 'windows' and path.suffix == '.sh':
                continue
            files.append(path)
    for path in sorted(set(files)):
        if not path.is_file() or path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('Missing or unsafe package source: ' + str(path))
        yield path.relative_to(root).as_posix(), path.read_bytes()


def add(archive, name, data, executable=False):
    info = zipfile.ZipInfo('cnki-download/' + name, (2026, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def build(root=ROOT, output=None):
    root = Path(root).resolve(); output = Path(output or root / 'dist').resolve()
    version = re.search(r'version:\s*"([^"]+)"', (root / 'SKILL.md').read_text(encoding='utf-8')).group(1)
    if not re.fullmatch(r'[0-9A-Za-z.-]+', version):
        raise ValueError('Invalid release version')
    output.mkdir(parents=True, exist_ok=True)
    hashes, artifacts = [], []
    for target in ('windows', 'macos'):
        path = output / ('academic-automation-v' + version + '-' + target + '.zip')
        with zipfile.ZipFile(path, 'w') as archive:
            for name, data in source_files(root, target):
                add(archive, name, data, name.endswith('.sh'))
            backend = 'extension' if target == 'windows' else 'apple-events'
            add(archive, 'platform.json', json.dumps({'platform': target, 'default_backend': backend,
                'version': version, 'validation': 'preview; see VERIFICATION.md'}, indent=2) + '\n')
            if target == 'windows':
                add(archive, 'academic.cmd', '@echo off\r\nwhere py >nul 2>nul\r\nif errorlevel 1 (\r\n  python "%~dp0scripts\\academic.py" %*\r\n) else (\r\n  py -3 "%~dp0scripts\\academic.py" %*\r\n)\r\nexit /b %errorlevel%\r\n')
            else:
                add(archive, 'academic.command', '#!/bin/sh\nexec python3 "$(dirname "$0")/scripts/academic.py" "$@"\n', True)
            instructions = (root / 'references' / ('install-' + target + '.md')).read_text(encoding='utf-8')
            # INSTALL.md is at the package root, one level above its source.
            instructions = re.sub(r'\]\(([^)]+)\)', lambda match: '](' + (
                match[1] if re.match(r'(?:[a-zA-Z][\w+.-]*:|/|#)', match[1])
                else 'references/' + match[1]) + ')', instructions)
            add(archive, 'INSTALL.md', instructions)
        hashes.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name)
        artifacts.append(path)
    (output / 'SHA256SUMS').write_text('\n'.join(hashes) + '\n', encoding='utf-8')
    return artifacts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output')
    args = parser.parse_args()
    for artifact in build(output=args.output): print(artifact)
