#!/usr/bin/env python3
# 更新下载状态清单中的某一行
# 用法: cnki_status.py "题名(可只给唯一片段)" "状态符号" "备注" "清单文件路径"
# 状态符号: ✅ ❌ ⚠️ ♻️
# 清单路径必须作为第 4 个参数传入，不要把本机路径写进脚本。
import sys

if len(sys.argv) < 5:
    print('用法: cnki_status.py "题名片段" "状态符号" "备注" "清单路径"')
    sys.exit(64)
t = sys.argv[1]
mark = sys.argv[2]
note = sys.argv[3] if sys.argv[3] else None
path = sys.argv[4]

s = open(path, encoding='utf-8').read()
lines = s.split('\n')
done = False
for i, l in enumerate(lines):
    if l.startswith('|') and t in l and ('⏳' in l or '❌' in l or '⚠️' in l):
        for old in ('⏳', '❌', '⚠️'):
            l = l.replace(old, mark)
        if note:
            l = l.rstrip()
            if l.endswith('|'):
                l = l[:-1].rstrip() + f' {note} |'
        lines[i] = l
        done = True
        break
if done:
    open(path, 'w', encoding='utf-8').write('\n'.join(lines))
print('updated' if done else 'NOT FOUND')
sys.exit(0 if done else 1)
