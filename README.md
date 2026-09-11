# Academic Automation Skill

> **2.0.0-beta.1 cross-platform preview:** shared Python core, Windows Chrome extension backend, and the existing macOS Apple Events backend. Windows website/extension and agent acceptance is pending. Download the Windows or macOS ZIP from the same Release; neither ZIP bundles runtimes. Start with [Windows installation](references/install-windows.md), [macOS installation](references/install-macos.md), and the [shared CLI](references/cli.md).


**English** | [简体中文](README.zh-CN.md)

> An AI skill for automating academic literature search and download workflows.

**Academic Automation Skill** is a personal AI Skill designed to help AI agents automate repetitive academic literature workflows through a web browser, including literature searching, preliminary filtering, downloading, and organization.

It currently supports **CNKI**, **Google Scholar**, and **Web of Science**.

This project is developed primarily through **Vibe Coding** and is continuously tested and improved through real-world academic literature workflows.

---

## Features

### Automated Literature Search

Search supported academic databases automatically based on research topics, keywords, and other criteria provided by the user.

### Literature Filtering

Perform preliminary filtering based on titles, keywords, abstracts, and other available metadata to reduce repetitive manual review.

### Literature Download

When the user already holds legitimate access to a paper, parts of the download process are automated.

Academic Automation Skill does **not** provide database accounts, subscriptions, institutional access, or paid content.

All access is performed through the **user's own browser, account, subscription, and/or institutional access privileges**.

### Literature Organization

Organize downloaded literature and related information to reduce repetitive post-download processing.

---

## Supported Platforms

| Platform | Status |
| --- | --- |
| CNKI | Supported |
| Google Scholar | Supported |
| Web of Science | Supported |

Academic platforms may change their page structures, authentication mechanisms, or access policies. Some automation features may therefore temporarily stop working after platform updates.

---

## Requirements

### Operating System

Windows 10/11: preview support through Playwright CLI and the official Chrome extension; real Windows acceptance is pending.

macOS: Apple Events remains the default; the extension backend is optional.

The shared core needs Python 3.9+. For new installations use a supported Python release. The extension backend also needs Node.js 22+ and the pinned npm dependencies. Linux support is limited to offline processing.

### Browser

Currently, this Skill works with:

**Google Chrome**

Authentication, institutional access, and database permissions are provided entirely by the user's own Chrome browser environment.

---

## Installation

The project is distributed as an **AI Skill**. Install it according to the Skill installation method supported by your AI Agent or Coding Agent.

Example (Codex / local skills folder):

```bash
cp -R . ~/.agents/skills/cnki-download
```

Agent instructions live in `SKILL.md`. The macOS default backend needs **Allow JavaScript from Apple Events**; the extension backend uses the platform installation instructions.

Tested with:

- OpenCode
- Qoder
- Cursor
- OpenAI Codex

Skill handling, browser automation, and tool invocation may differ between agents, so identical behavior across all environments is not guaranteed.

---

## How It Works

Academic Automation Skill works through an AI agent controlling the user's own Chrome browser. Based on the research topic, keywords, or search criteria provided by the user, it interacts with supported academic databases to perform searching, filtering, downloading, and organization.

Academic Automation Skill **does not provide access privileges to any academic database**.

If an article requires a subscription, purchase, or institutional authorization, the user must already have the appropriate access rights.

---

## Accounts & Access

This project:

- does not provide CNKI, Google Scholar, or Web of Science accounts;
- does not contain the developer's database credentials;
- does not share the developer's authenticated sessions;
- does not provide institutional subscriptions;
- does not provide a method to obtain paid literature for free.

When accessing academic databases through this Skill, users must use:

**their own browser + their own account + their own authorized access privileges.**

---

## CAPTCHA

Academic Automation Skill **does not automatically bypass CAPTCHAs or similar human-verification mechanisms**.

If a website requires a CAPTCHA or another interactive verification step, automation should pause and allow the user to complete it manually before continuing.

---

## Third-Party Services

Academic Automation Skill is an independent personal project.

This project is not officially affiliated with, sponsored by, endorsed by, or associated with **CNKI**, **Google Scholar**, **Web of Science**, or their respective operators.

All product names and trademarks belong to their respective owners.

Users are responsible for ensuring that their use of Academic Automation Skill complies with the applicable terms and policies of academic databases, institutional subscriptions, and network environments.

Academic Automation Skill does not circumvent authentication, paywalls, CAPTCHAs, or other access-control mechanisms.

---

## Responsible Use

The goal of Academic Automation Skill is to: **reduce repetitive and mechanical browser operations in academic research workflows.** It is not designed to grant users access privileges that have not already been provided by the relevant database or institution.

Please use automation at a reasonable scale and frequency and respect the applicable rules of academic databases and institutions.

---

## Development

This is a personal project developed primarily through **Vibe Coding**.

Project requirements, feature direction, testing, and final release decisions are handled by the project maintainer, with extensive assistance from generative AI for coding, debugging, refactoring, documentation, and design discussions.

Major AI tools used during development include:

- **Cursor**
- **ChatGPT by OpenAI**

AI-assisted development is an intentional part of this project's development process and is therefore disclosed here explicitly.

---

## Current Status

Academic Automation Skill is under active development.

Current priorities include:

- improving search reliability across academic databases;
- improving literature filtering and organization;
- adapting to changes in database page structures;
- testing compatibility with different AI agents;
- developing and testing Windows support with other contributors.

Bug reports, testing feedback, and compatibility reports are welcome.

---

## Changelog

- **1.6.0** (2026-09-12) — Lower initial context use and resumable workflows:
  - Load workflow and troubleshooting references only when needed; reduce `SKILL.md` from 13,696 to 3,108 characters (77.3%).
  - Wait for stable page content and completed downloads; preserve WoS records recycled by virtual scrolling and detect download-time paywalls or CAPTCHA prompts.
  - Resume search pages and metadata collection, deduplicate batch entries by document identity, and reuse a 24-hour professional-search index with live detail verification.
  - Require the first author before starting Chinese downloads; use shared single-tab navigation for unknown publishers.
  - Add 16 regression tests and [verification results](VERIFICATION.md) covering live CNKI, WoS, Scholar, and OA download workflows.
- **1.5.1** (2026-08-26) — Chinese library matching and file handling fixes: title search now goes through `korder=TI`; exact matches take priority (several substring matches no longer resolve to the first row); a short title without an author exits with code 64; `--affiliation` carries `TI=`/`AU=` as well; the detail, paywall, and verification pages are polled before and after the download click; files are archived by mtime; after a CAPTCHA the downloaded file is checked first; single-tab navigation now covers WoS, Scholar, and the foreign library; status tables accept two header layouts; bibliographic entries without a URL are no longer written into the list.
- **1.5.0** (2026-08-26) — Download stability for the Chinese library:
  - `cnki_dl.sh`: author check on the result row (titles of 6 characters or fewer require an author); `--expert` professional search (`SU='A' AND SU='B'`, which works around the advanced search button that ignores injected clicks); `--affiliation` institution filter; `《》〈〉""——` are stripped from the search URL automatically; NOMATCH scans up to 3 result pages (`--pages`); single-tab `set URL` with `window.stop()` before navigating; exit code 5 recognizes the paywall page at `bar.cnki.net/bar/fee`.
  - Added `scripts/cnki_batch.py`: `i/N` progress, an idempotent status table located by row number, pause and resume on CAPTCHA, and cleanup of surplus tabs in the front window every 10 papers.
  - Added `scripts/cnki_next.js` and `scripts/cnki_url.js`.
  - `SKILL.md`: scan the workspace before starting, how to use professional search, and "known pitfalls" (zsh `IFS`, cross-device `shutil.move`, JS return values, and how long `bar.cnki.net` order pages take).
- **1.4.1** — CNKI foreign library (WWJD), quoted phrase search, DOI completion, publisher OA routing (`oa_dl.sh`), and the Web of Science / Google Scholar workflows.

---

## Disclaimer

This project provides browser automation and academic-workflow assistance only.

Academic Automation Skill does not host, sell, or redistribute full-text literature from CNKI, Google Scholar, Web of Science, or other third-party databases.

Database access performed through this project relies on the user's own browser environment, account, and access privileges.

The project maintainer cannot guarantee that third-party websites will always permit, support, or remain technically compatible with automated access. Terms of service, technical measures, and access policies may change over time.

Users are responsible for determining whether their specific use complies with applicable platform rules, institutional license agreements, and laws and regulations.

---

*Academic Automation Skill is a personal project and is still evolving. If something breaks after an academic database updates its website, feel free to open an issue.*
