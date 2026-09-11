#!/usr/bin/env python3
# CNKI 批量下载驱动：清单 -> 共享 CLI -> 进度/状态表/人工暂停续传
# 用法: cnki_batch.py 清单.txt [--expert "SU='A' AND SU='B'"] [--affiliation "机构"] [--pages 3] [--dl /path/to/cnki_dl.sh]
# 清单格式（竖线分隔；# 开头为注释行，空行跳过）：
#   题名|第一作者|目标文件夹
#   所有条目必须给第一作者；文件夹可留空（默认 ./downloads）。
# 状态表：<清单名>.状态.md 为视图；.progress.json 按文献身份和实际文件验证续跑。
# 验证码（cnki_dl.sh 退出码 2）：暂停等用户完成拼图；回车后先按作者后缀检查 ~/Downloads 是否已落盘，
# 已落盘则归档当前篇，不再整段重跑（避免打断知网 returnUrl）。
import argparse
import os
import re
import subprocess
import sys
import time
import hashlib
from pathlib import Path
from .browser_runtime import atomic_json, read_json, BrowserError
from .download_watch import snapshot, wait_download, archive, valid_file
from .cnki_index import norm
from .paths import SCRIPTS

EXIT_MAP = {
    0: ('✅', '已下载'),
    1: ('❌', '未匹配/无结果'),
    2: ('⏸', '验证码，待人工后重试'),
    3: ('❌', '详情页无下载链接'),
    4: ('❌', '文件未落盘'),
    5: ('⚠️', '收费页/不在机构权限内'),
    64: ('❌', '参数错误'),
}


def parse_list(path):
    items = []
    with open(path, encoding='utf-8') as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) > 3:
                print(f'清单第 {ln} 行竖线多于 3 段，已按前 3 段处理: {line}')
            title = parts[0] if parts else ''
            author = parts[1] if len(parts) > 1 else ''
            folder = parts[2] if len(parts) > 2 else ''
            if not title:
                print(f'清单第 {ln} 行缺题名，跳过')
                continue
            items.append((title, author, folder))
    return items


def state_path(list_path):
    root, ext = os.path.splitext(list_path)
    return root + '.状态.md'


def write_state(path, items, rows):
    head = '| 序号 | 状态 | 题名 | 备注 |', '|---|---|---|---|'
    lines = [head[0], head[1]]
    for i, (title, author, _folder) in enumerate(items, 1):
        lines.append(rows.get(i, f'| {i} | ⏳ | {title} | {"待下载" if not author else "待下载 " + author} |'))
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def set_row(rows, idx, mark, title, note):
    rows[idx] = f'| {idx} | {mark} | {title} | {note} |'


def identity(title, author, folder):
    return hashlib.sha256(('\0'.join((norm(title), author.strip(), str(Path(folder).resolve())))).encode()).hexdigest()


def file_record(path):
    p = Path(path).resolve()
    if not valid_file(p):
        return None
    stat = p.stat()
    return {'path': str(p), 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}


def verified(record):
    if not isinstance(record, dict) or not record.get('path'):
        return False
    return file_record(record['path']) == {k: record[k] for k in ('path', 'size', 'mtime_ns') if k in record}


def existing_exact(title, author, folder):
    """Import legacy/existing assets only with exact normalized title AND author."""
    if not Path(folder).is_dir():
        return None
    hits = []
    for p in Path(folder).iterdir():
        stem = re.sub(r' \(\d+\)$', '', p.stem)
        suffix = '_' + author
        if (not p.name.startswith('._') and stem.endswith(suffix)
                and norm(stem[:-len(suffix)]) == norm(title) and valid_file(p)):
            hits.append(p)
    return hits[0] if len(hits) == 1 else None


def main():
    ap = argparse.ArgumentParser(description='CNKI 批量下载驱动')
    ap.add_argument('list', help='清单文件：题名|第一作者|目标文件夹')
    ap.add_argument('--expert', default='', help="专业检索表达式，如 \"SU='学习进阶' AND SU='化学'\"")
    ap.add_argument('--affiliation', default='', help="机构过滤，转发给 cnki_dl.sh --affiliation")
    ap.add_argument('--pages', type=int, default=3, help='NOMATCH 自动翻页上限（默认 3）')
    ap.add_argument('--refresh-index', action='store_true', help='重建专业检索链接索引')
    ap.add_argument('--dl', default='', help='Optional legacy download command override')
    ap.add_argument('--retry', action='store_true', help='Retry requests after inspecting pending downloads')
    args = ap.parse_args()
    if args.pages < 0:
        print('Invalid --pages', file=sys.stderr)
        sys.exit(64)

    items = parse_list(args.list)
    if not items:
        print('清单为空')
        sys.exit(64)
    missing = [str(i) for i, (_, author, _) in enumerate(items, 1) if not author.strip()]
    if missing:
        print('以下条目缺少第一作者，尚未打开浏览器：' + ', '.join(missing))
        sys.exit(64)
    sp = state_path(args.list)
    rows = {}  # Markdown is a view; never infer identity from a row number or emoji.
    cp = str(Path(args.list).with_suffix('.progress.json'))
    manifest = read_json(cp, {'version': 1, 'records': {}})
    records = manifest.setdefault('records', {})
    index = str(Path(args.list).with_suffix('.search-index.json'))
    if args.refresh_index and Path(index).exists():
        Path(index).unlink()
    total = len(items)
    fails = []
    attempted = {}
    downloads = os.environ.get('CNKI_DOWNLOADS_DIR', os.path.expanduser('~/Downloads'))
    for i, (title, author, folder) in enumerate(items, 1):
        folder = folder or 'downloads'
        key = identity(title, author, folder)
        record = records.get(key)
        found = existing_exact(title, author, folder) if record is None else None
        if found:
            record = file_record(found)
            records[key] = record
            atomic_json(cp, manifest)
        if verified(record):
            set_row(rows, i, '✅', title, '已核验 ' + record['path'])
            write_state(sp, items, rows)
            print(f'[{i}/{total}] 跳过（文献身份及文件已核验）: {title}')
            continue
        if key in attempted:
            mark, label = attempted[key]
            set_row(rows, i, mark, title, '本批重复条目：' + label)
            write_state(sp, items, rows)
            fails.append((i, title, label))
            continue
        cmd = [args.dl] if args.dl else [sys.executable, str(SCRIPTS / 'academic.py'), 'download', 'cnki']
        if args.retry and not args.dl:
            cmd += ['--retry']
        if args.expert:
            cmd += ['--expert', args.expert]
            cmd += ['--index', index]
        if args.affiliation:
            cmd += ['--affiliation', args.affiliation]
        cmd += ['--pages', str(args.pages)]
        cmd += [title, author, folder]
        r = None
        for tri in range(3):
            print(f'[{i}/{total}] 下载: {title} {author} -> {folder}')
            since = time.time()
            before = snapshot(downloads)
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
            print(r.stdout, end='', flush=True)
            archived = ''
            if r.returncode == 0:
                archived = next((line[len('ARCHIVED: '):] for line in r.stdout.splitlines()
                                 if line.startswith('ARCHIVED: ')), '')
            if r.returncode == 2:
                set_row(rows, i, '⏸', title, '待人工处理；处理后重跑同一命令')
                write_state(sp, items, rows)
                if not args.dl:
                    # Single-download checkpoints survive process exit. Do not block an
                    # agent tool on input() or navigate away from the pending article.
                    sys.exit(2)
                try:
                    input(f'  验证码：请在 Chrome 完成拼图验证后回车（第 {tri + 1}/3 次）… ')
                except EOFError:
                    sys.exit(2)
                try:
                    path = wait_download(downloads, before, author, since, timeout=40)
                    archived = str(archive(path, folder))
                    r = subprocess.CompletedProcess(cmd, 0)
                    break
                except BrowserError as e:
                    if e.code != 4: raise
                continue
            break
        if r is None:
            continue
        mark, label = EXIT_MAP.get(r.returncode, ('❌', f'未知退出码 {r.returncode}'))
        if r.returncode == 0:
            record = file_record(archived) if archived else None
            if not record:
                found = existing_exact(title, author, folder)
                record = file_record(found) if found else None
            if record:
                records[key] = record
                atomic_json(cp, manifest)
                label = '已下载 ' + record['path']
            else:
                r = subprocess.CompletedProcess(cmd, 4)
                mark, label = '❌', '成功返回但归档文件未通过核验'
        attempted[key] = (mark, label)
        set_row(rows, i, mark, title, label)
        write_state(sp, items, rows)
        if r.returncode != 0:
            fails.append((i, title, label))
        if i < total:
            time.sleep(2)  # pacing independent of page readiness
    print(f'\n完成：成功 {sum(1 for i_ in range(1, total + 1) if "✅" in rows.get(i_, ""))}/{total}'
          f'，状态表: {sp}')
    if fails:
        print('未成功清单：')
        for i, title, label in fails:
            print(f'  {i}. {title} —— {label}')
        sys.exit(1)


if __name__ == '__main__':
    main()
