# AGENTS.md

This repository is the `cnki-download` AI Skill, not a hosted app.

## Architecture

- `scripts/academic.py` is the portable public CLI. `src/academic_automation/` owns Python business logic; the old `.py` and macOS `.sh` entry points are compatibility wrappers.
- JavaScript in `scripts/` is injected into a browser page. It is not standalone Node application code.
- Python core uses only the standard library (Python 3.9+). The optional extension backend uses the pinned `@playwright/cli` in `package.json` and `package-lock.json`; install with `npm ci --ignore-scripts`.
- macOS defaults to Apple Events; Windows uses the official Playwright Chrome extension. Use the logged-in user's selected tab, never export cookies or copy a browser profile. Agent clients use the same CLI, not client-specific tools.
- Browser operations acquire the shared local lock. Batch pauses with exit 2 and checkpoints instead of waiting on stdin; manual recovery checks files before issuing another request.
- `needs_user` persists an interaction handoff across commands. Do not equate it with an unavailable paper. Only an actual user reply authorizes `browser resolve`; automatic file recovery may complete an already saved download first. Keep legacy entry points on the same guard and exit-code contract.

## Verification

- Offline: `python3 -B -X utf8 -m unittest discover -s tests -v`. Node is used for JavaScript fixture tests; no website or account is accessed.
- Opt-in isolated Chrome transport test: set `ACADEMIC_BROWSER_TESTS=1` and run the tests after installing npm dependencies. This does not validate the official extension or institution sessions.
- Package: `python3 scripts/build_release.py`; creates two ZIPs and SHA256SUMS in ignored `dist/`, without publishing or tagging.
- Real platform/site/Agent acceptance is documented in `references/acceptance.md` and `VERIFICATION.md`. Windows real-world testing is assigned to a tester and must not be claimed from macOS results.
- On Linux, offline processing/tests/building are usable. Do not claim end-to-end academic-browser support without a logged-in desktop browser and specific evidence.

## Maintenance

Keep wrappers compatible, return structured CLI statuses, preserve title/author verification, CNKI page referrer, file checks, and no-overwrite archiving. Update the version only in SKILL.md; package names read that value. Never package browser state, tokens, downloaded papers, node_modules, or local caches. Do not replace source URLs or real metadata with guessed values.
