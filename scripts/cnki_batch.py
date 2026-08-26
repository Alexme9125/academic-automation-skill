#!/usr/bin/env python3
# CNKI 批量下载驱动：清单 -> 逐篇调 cnki_dl.sh -> 进度/状态表/验证码暂停续传
# 用法: cnki_batch.py 清单.txt [--expert "SU='A' AND SU='B'"] [--affiliation "机构"] [--pages 3] [--dl /path/to/cnki_dl.sh]
# 清单格式（竖线分隔；# 开头为注释行，空行跳过）：
#   题名|第一作者|目标文件夹
#   作者可留空（短题名必须给全，否则 cnki_dl.sh 退出 64），文件夹可留空（默认 ./downloads）。
# 状态表：默认写在 清单路径同目录的 <清单名>.状态.md，按序号行定位、幂等；重跑时跳过已 ✅ 的条目。
# 验证码（cnki_dl.sh 退出码 2）：暂停等用户完成拼图；回车后先按作者后缀检查 ~/Downloads 是否已落盘，
# 已落盘则归档当前篇，不再整段重跑（避免打断知网 returnUrl）。
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

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
    return root + '.状态' + (ext or '.md')


STATUS_RE = re.compile(r'^\|\s*(\d+)\s*\|')


def load_state(path):
    """读状态表 -> {序号(1起): 行文本}。序号定位，不靠字符串匹配，天然幂等。"""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = STATUS_RE.match(line.rstrip('\n'))
            if m:
                rows[int(m.group(1))] = line.rstrip('\n')
    return rows


def write_state(path, items, rows):
    head = '| 序号 | 状态 | 题名 | 备注 |', '|---|---|---|---|'
    lines = [head[0], head[1]]
    for i, (title, author, _folder) in enumerate(items, 1):
        lines.append(rows.get(i, f'| {i} | ⏳ | {title} | {"待下载" if not author else "待下载 " + author} |'))
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def set_row(rows, idx, mark, title, note):
    rows[idx] = f'| {idx} | {mark} | {title} | {note} |'


def pick_dl(author, since):
    if not author:
        return ''
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cnki_pick_dl.py')
    downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
    r = subprocess.run(
        [sys.executable, script, downloads, author, str(int(since))],
        capture_output=True, text=True)
    return (r.stdout or '').strip()


def archive_found(src, folder):
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, os.path.basename(src))
    shutil.move(src, dest)
    return dest


def wait_captcha_file(author, folder, since, rounds=20):
    """验证码通过后 returnUrl 可能已触发下载：先轮询落盘，避免整段重跑。"""
    for _ in range(rounds):
        time.sleep(2)
        path = pick_dl(author, since)
        if path:
            dest = archive_found(path, folder)
            print(f'  验证后已落盘: {os.path.basename(dest)}')
            return dest
    return ''


def main():
    ap = argparse.ArgumentParser(description='CNKI 批量下载驱动')
    ap.add_argument('list', help='清单文件：题名|第一作者|目标文件夹')
    ap.add_argument('--expert', default='', help="专业检索表达式，如 \"SU='学习进阶' AND SU='化学'\"")
    ap.add_argument('--affiliation', default='', help="机构过滤，转发给 cnki_dl.sh --affiliation")
    ap.add_argument('--pages', type=int, default=3, help='NOMATCH 自动翻页上限（默认 3）')
    ap.add_argument('--dl', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cnki_dl.sh'),
                    help='cnki_dl.sh 路径')
    args = ap.parse_args()

    items = parse_list(args.list)
    if not items:
        print('清单为空')
        sys.exit(64)
    sp = state_path(args.list)
    rows = load_state(sp)
    total = len(items)
    fails = []
    for i, (title, author, folder) in enumerate(items, 1):
        if i in rows and '✅' in rows[i]:
            print(f'[{i}/{total}] 跳过（已 ✅）: {title}')
            continue
        folder = folder or 'downloads'
        cmd = [args.dl]
        if args.expert:
            cmd += ['--expert', args.expert]
        if args.affiliation:
            cmd += ['--affiliation', args.affiliation]
        cmd += ['--pages', str(args.pages)]
        cmd += [title, author, folder]
        r = None
        for tri in range(3):
            print(f'[{i}/{total}] 下载: {title} {author} -> {folder}')
            since = time.time()
            r = subprocess.run(cmd)
            if r.returncode == 2:
                input(f'  验证码：请在 Chrome 完成拼图验证后回车（第 {tri + 1}/3 次）… ')
                if wait_captcha_file(author, folder, since):
                    r = subprocess.CompletedProcess(cmd, 0)
                    break
                continue
            break
        if r is None:
            continue
        mark, label = EXIT_MAP.get(r.returncode, ('❌', f'未知退出码 {r.returncode}'))
        set_row(rows, i, mark, title, label)
        write_state(sp, items, rows)
        if r.returncode != 0:
            fails.append((i, title, label))
    print(f'\n完成：成功 {sum(1 for i_ in range(1, total + 1) if "✅" in rows.get(i_, ""))}/{total}'
          f'，状态表: {sp}')
    if fails:
        print('未成功清单：')
        for i, title, label in fails:
            print(f'  {i}. {title} —— {label}')
        sys.exit(1)


if __name__ == '__main__':
    main()
