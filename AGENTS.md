# AGENTS.md

## Cursor Cloud specific instructions

This repo is an **AI Skill** (`cnki-download`, see `SKILL.md`), not a server/app. It has no
package manager, dependencies, lockfiles, build system, test suite, linter, or CI. It is
consumed by an AI agent that follows `SKILL.md` and invokes the scripts in `scripts/`.

### Platform reality in the cloud VM (Linux)
- The end-to-end product is **macOS-only**: the `*.sh` wrappers and `*.js` snippets drive a
  logged-in Google Chrome via `osascript` (Apple Events). `osascript`/Apple Events do **not**
  exist on the Linux cloud VM, so the browser-automation flow (CNKI / Web of Science / Google
  Scholar search + download) **cannot be run or demonstrated here**. The `.js` files are Chrome-
  injected snippets (they reference `document`/`window`), not standalone Node programs.
- What **is** runnable/testable on Linux is the cross-platform Python data-processing layer
  (the "literature organization" core). These use only the Python standard library:
  - `scripts/gs_bib.py`, `scripts/wos_bib.py`, `scripts/cnki_bib.py` — turn a search-result
    JSON (`{"rows": [...]}` or a bare array) into a linked Markdown bibliography.
  - `scripts/cnki_status.py` — update one row in a `下载状态.md` status table.
  - `scripts/pdf_pages.py` — print a PDF's page count. On Linux `mdls` is absent, so it uses the
    built-in byte-parsing fallback automatically (works without any extra tools).

### How to verify the environment (no install needed)
- Interpreters are preinstalled: `python3` (3.12) and `node` (22).
- Syntax check everything (closest thing to lint/build):
  - `python3 -m py_compile scripts/*.py`
  - `for f in $(find scripts -name '*.js'); do node --check "$f"; done`
- Smoke-test the Python core by feeding a small JSON to a `*_bib.py` script and inspecting the
  generated Markdown, e.g. `python3 scripts/gs_bib.py in.json out.md --title "..."`.
