#!/usr/bin/env python3
# 打印 PDF 页数。mdls 对新文件常返回 null，回退解析 PDF /Count。
# 用法: pdf_pages.py /path/to/file.pdf
import re, subprocess, sys

def mdls_pages(path: str):
    try:
        raw = subprocess.check_output(
            ['mdls', '-name', 'kMDItemNumberOfPages', '-raw', path],
            text=True, stderr=subprocess.DEVNULL).strip()
        if raw.isdigit():
            return int(raw)
    except Exception:
        return None
    return None

def pdf_count(path: str):
    try:
        data = open(path, 'rb').read(8_000_000)
    except Exception:
        return None
    if not data.startswith(b'%PDF'):
        return None
    found = re.findall(rb'/Type\s*/Pages\b.{0,400}?/Count\s+(\d+)', data, re.S)
    if not found:
        found = re.findall(rb'/Count\s+(\d+)', data)
    nums = [int(x) for x in found if 0 < int(x) < 10000]
    return max(nums) if nums else None

def main():
    if len(sys.argv) < 2:
        print('null')
        sys.exit(64)
    path = sys.argv[1]
    n = mdls_pages(path)
    if n is None:
        n = pdf_count(path)
    print(n if n is not None else 'null')

if __name__ == '__main__':
    main()
