#!/usr/bin/env python3
# 在下载目录里挑「mtime >= since、后缀 _作者.pdf|.caj」里最新的一个。
# 用法: cnki_pick_dl.py <文件夹> <第一作者> <since_epoch>
# 作者为空则不输出（避免匹配 *_ .pdf）。不按 find 目录序，按修改时间。
import os
import sys


def main():
    if len(sys.argv) < 4:
        print('用法: cnki_pick_dl.py <文件夹> <第一作者> <since_epoch>', file=sys.stderr)
        sys.exit(64)
    folder, author, since_s = sys.argv[1], sys.argv[2], sys.argv[3]
    if not author:
        return
    try:
        since = float(since_s)
    except ValueError:
        sys.exit(64)
    suffixes = (
        f'_{author}.pdf',
        f'_{author}.caj',
        f'_{author}.PDF',
        f'_{author}.CAJ',
    )
    try:
        names = os.listdir(folder)
    except OSError:
        return
    cands = []
    for name in names:
        if name.startswith('._'):
            continue
        if not name.endswith(suffixes):
            continue
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        try:
            m = os.path.getmtime(path)
        except OSError:
            continue
        if m + 2 >= since:
            cands.append((m, path))
    if not cands:
        return
    cands.sort(reverse=True)
    print(cands[0][1])


if __name__ == '__main__':
    main()
