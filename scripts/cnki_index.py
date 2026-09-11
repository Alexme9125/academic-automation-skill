#!/usr/bin/env python3
"""Short-lived expert-query index. Cached hits still require live detail verification."""
import argparse
import json
import re
import sys
import time
from browser_runtime import atomic_json, read_json, run_file, run_js, navigate, wait_ready, BrowserError


def norm(s):
    return re.sub(r'''[\s:：，,。.、；;！!？?《》〈〉()（）\-—·“”‘’"']''', '', s or '')


def select(pages, title, author):
    """Same exact-first and author rule as the live matcher; ambiguity never picks first."""
    exact, partial = {}, []
    target = norm(title)
    for page in pages:
        matches = []
        for row in page:
            text = norm(row.get('title', ''))
            if author not in row.get('text', ''):
                continue
            if text == target:
                exact[row['href']] = row
            elif len(target) >= 4 and target in text:
                matches.append(row)
        if len(matches) == 1:
            partial.extend(matches)
    if len(exact) == 1:
        return next(iter(exact.values()))
    if exact:
        return None
    unique = {r['href']: r for r in partial}
    return next(iter(unique.values())) if len(unique) == 1 else None


def load_index(path, query, pages):
    data = read_json(path, {})
    if (data.get('query') == query and data.get('limit') == pages
            and time.time() - data.get('created', 0) < 86400 and data.get('complete')):
        return data
    return None


def build(path, query, limit):
    origin = run_js('location.href')
    pages = []
    for i in range(max(1, limit)):
        state = wait_ready('cnki-results', 20, minimum=2)
        raw = json.loads(run_file('cnki_rows.js'))
        if not raw.get('rows'):
            raise BrowserError('INDEX_EMPTY')
        pages.append(raw['rows'])
        if i + 1 >= max(1, limit):
            break
        if not run_file('cnki_next.js').startswith('next'):
            break
        try:
            wait_ready('cnki-results', 15, previous=state['signature'], minimum=2)
        except BrowserError as e:
            if e.code == 2:
                raise
            # Never cache a page whose transition/completeness could not be verified.
            navigate(origin)
            wait_ready('cnki-results', 20, minimum=2)
            raise
    data = {'query': query, 'limit': limit, 'created': time.time(), 'complete': True, 'pages': pages}
    atomic_json(path, data)
    return data, origin


def verify_detail(title, author):
    wait_ready('cnki-meta', 20)
    # The first h1 can be CNKI's hidden "自动登录" template, not the article title.
    data = json.loads(run_js('''JSON.stringify({title:document.title,
      body:document.querySelector('.author')?.textContent?.trim() || (document.body?document.body.innerText:'')})'''))
    page_title = norm(re.sub(r'\s*-\s*中国知网\s*$', '', data['title']).strip())
    return page_title == norm(title) and author in data['body']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['lookup', 'build', 'verify'])
    ap.add_argument('path'); ap.add_argument('query'); ap.add_argument('pages', type=int)
    ap.add_argument('title'); ap.add_argument('author')
    args = ap.parse_args()
    try:
        if args.command == 'verify':
            sys.exit(0 if verify_detail(args.title, args.author) else 1)
        data = load_index(args.path, args.query, args.pages)
        origin = ''
        if args.command == 'build':
            data, origin = build(args.path, args.query, args.pages)
        hit = select(data['pages'], args.title, args.author) if data else None
        if hit:
            print(hit['href'])
        elif origin:
            navigate(origin)
            wait_ready('cnki-results', 20, minimum=2)
    except BrowserError as e:
        print(str(e), file=sys.stderr); sys.exit(e.code)


if __name__ == '__main__':
    main()
