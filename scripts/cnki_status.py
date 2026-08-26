#!/usr/bin/env python3
# 更新下载状态清单中的某一行
# 用法: cnki_status.py "题名(可只给唯一片段)" "状态符号" "备注" "清单文件路径"
# 状态符号: ✅ ❌ ⚠️ ♻️ ⏸
# 同时支持两种表头：
#   | ⏳ | 题名 | 第一作者 | 编号 | 备注 |
#   | 序号 | 状态 | 题名 | 备注 |   （cnki_batch.py）
# 只改状态列，不在整行 replace 表情符号（避免误伤题名）。
import re
import sys

PENDING = ('⏳', '❌', '⚠️', '⏸')


def cells(line):
    if not line.startswith('|'):
        return None
    body = line.strip()
    if body.startswith('|'):
        body = body[1:]
    if body.endswith('|'):
        body = body[:-1]
    return [p.strip() for p in body.split('|')]


def is_sep(parts):
    if not parts:
        return True
    return all(re.fullmatch(r':?-{3,}:?', p or '') for p in parts)


def join_cells(parts):
    return '| ' + ' | '.join(parts) + ' |'


def main():
    if len(sys.argv) < 5:
        print('用法: cnki_status.py "题名片段" "状态符号" "备注" "清单路径"')
        sys.exit(64)
    t = sys.argv[1]
    mark = sys.argv[2]
    note = sys.argv[3] or ''
    path = sys.argv[4]

    lines = open(path, encoding='utf-8').read().split('\n')
    done = False
    for i, l in enumerate(lines):
        parts = cells(l)
        if not parts or len(parts) < 2 or is_sep(parts):
            continue
        if parts[0] in ('序号',) or '题名' in parts:
            continue
        blob = '|'.join(parts)
        if t not in blob:
            continue
        if parts[0].isdigit() and len(parts) >= 3:
            status_i, title_i, note_i = 1, 2, 3 if len(parts) > 3 else None
        else:
            status_i, title_i, note_i = 0, 1 if len(parts) > 1 else 0, len(parts) - 1
        if t not in parts[title_i]:
            continue
        if not any(s in parts[status_i] for s in PENDING):
            continue
        parts[status_i] = mark
        if note and note_i is not None:
            while len(parts) <= note_i:
                parts.append('')
            parts[note_i] = note
        lines[i] = join_cells(parts)
        done = True
        break
    if done:
        open(path, 'w', encoding='utf-8').write('\n'.join(lines))
    print('updated' if done else 'NOT FOUND')
    sys.exit(0 if done else 1)


if __name__ == '__main__':
    main()
