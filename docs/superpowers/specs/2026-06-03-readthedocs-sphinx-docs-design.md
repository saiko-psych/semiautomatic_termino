# Read the Docs (Sphinx + MyST) — Design Spec

- **Date:** 2026-06-03
- **Topic:** Host the `semiautomatic_termino` project documentation on readthedocs.io
- **Status:** Approved (brainstorming) — pending spec review, then implementation plan
- **Author:** David + Claude (brainstorming session)

---

## 1. Goal

Publish a versioned, navigable documentation site for the project on
`readthedocs.io`, built with **Sphinx + MyST (Markdown)**. The site must:

- Render the existing prose docs (install, configuration, secrets, VPN,
  deployment, troubleshooting, architecture) as a structured multi-page site.
- Include a **full auto-generated API reference** from the `utils/` module
  docstrings (Sphinx `autodoc` + `autosummary`).
- Carry **web screenshots** (Termino, uniCLOUD/Nextcloud) with all
  sensitive / personal data blurred.
- Be in **English** (consistent with the README and the distribution intent).
- Survive ongoing project churn: the **structure** is the durable artifact;
  page content is loosely sourced from the current README, not tightly coupled
  to its present wording.

## 2. Decisions (locked during brainstorming)

| Aspect | Decision |
|---|---|
| Generator | Sphinx + MyST (`myst-parser`) |
| Theme | `furo` |
| API docs | Full `autodoc`/`autosummary` over all `utils/` modules |
| Mock strategy | Install real deps on RTD; mock **only** Linux-unimportable (Windows) modules — list determined empirically |
| Language | English |
| Hosting | readthedocs.io via `.readthedocs.yaml` |
| Content strategy | "Split & Adapt" — durable scaffold, loose sourcing from README, stubs where the project is still in flux |
| Screenshots | Web-based (Termino, uniCLOUD/Nextcloud); blurred PII; generated **once, locally**, committed as PNGs; **not** part of the RTD build |
| Screenshot tool | **Playwright**, isolated as a **dev/docs-only** optional dependency (never a runtime dep, never on the server or RTD) |

## 3. Non-goals (YAGNI)

- **No i18n / bilingual docs.** English only for now. `sphinx-intl` can be
  added later if a German edition is ever needed.
- **No screenshots in the RTD build pipeline.** RTD has no VPN and no
  credentials; it could never reach the authenticated pages. PNGs are
  pre-rendered and committed.
- **No screenshots of native desktop / terminal UIs via Playwright** (Cisco
  Secure Client, openconnect-gui, Credential Manager, Task Scheduler,
  PowerShell wizards). Playwright cannot capture non-browser surfaces; those
  stay as manual OS screenshots or code blocks, out of scope for this task.
- **No deep coupling to the current README wording** — it will change.

## 4. Architecture — directory layout

```
.readthedocs.yaml              # RTD build config
docs/
  conf.py                      # Sphinx config (myst, autodoc, autosummary, furo, mock_imports)
  index.md                     # Landing page + root toctree
  getting-started/
    installation.md            # sourced from README "Quick install"
    configuration.md           # sourced from README "Configuration"
    secrets.md                 # sourced from README "Storing secrets"
  usage/
    daily-run.md               # sourced from README "Daily run" + "Email templates"
  deployment/
    server-cron.md             # sourced from README "Server/cron" + SERVER_DEPLOY_PLAN.md
    vpn-setup.md               # sourced from docs/SERVER_VPN_SETUP.md + README VPN section
  architecture/
    overview.md                # Provider pattern (3x factory)
  reference/
    api/
      index.md                 # autosummary entry point -> per-module stubs
  troubleshooting.md           # sourced from README "Troubleshooting"
  _static/
    screenshots/               # committed, blurred PNGs (referenced by the prose pages)
  superpowers/specs/           # this spec lives here (already created)
```

Notes:
- `docs/` already contains `SERVER_VPN_SETUP.md` and
  `UNIGRAZ_OPENCONNECT_ROADMAP.md`; there is **no** `conf.py` yet, so this is a
  greenfield Sphinx setup with no collision.
- The two existing `docs/*.md` files are folded into the new structure
  (vpn-setup.md / a roadmap appendix) rather than left loose.

## 5. Tooling & dependencies

Add two **optional** dependency groups to `pyproject.toml` (neither touches the
runtime install used by `main.py`):

```toml
[project.optional-dependencies]
docs = [
    "sphinx>=8.0",
    "myst-parser>=4.0",
    "furo>=2024.8",
    "sphinx-copybutton>=0.5",      # copy buttons on code blocks
    "sphinx-autodoc-typehints>=2.0", # nicer rendered type hints
]
screenshots = [
    "playwright>=1.48",            # dev/docs-only; `playwright install chromium` separately
]
```

- Local docs build: `uv sync --extra docs` then `uv run sphinx-build -b html docs docs/_build/html`.
- Screenshot tool: `uv sync --extra screenshots` + `uv run playwright install chromium`.
- The `screenshots` extra is deliberately **separate** from `docs` so a plain
  docs build never pulls a browser.

## 6. RTD build config (`.readthedocs.yaml`)

```yaml
version: 2

build:
  os: ubuntu-24.04
  tools:
    python: "3.12"

sphinx:
  configuration: docs/conf.py

python:
  install:
    - method: pip
      path: .
      extra_requirements:
        - docs
```

Rationale: `pip install .[docs]` installs the **real** project (so autodoc sees
real signatures) plus the docs toolchain. Platform markers in `pyproject.toml`
mean Linux-only/Windows-only deps resolve correctly on the RTD container
(e.g. `pywin32` is skipped on Linux; `keyrings.alt` installs).

**Alternative considered (rejected):** a slim `docs/requirements.txt` with
Sphinx only + a large `autodoc_mock_imports` list. Rejected because maintaining
a big mock list is fragile and produces less faithful API docs. The chosen
approach mocks only what genuinely cannot import on Linux.

## 7. Sphinx config (`conf.py`) — key points

- Extensions: `myst_parser`, `sphinx.ext.autodoc`, `sphinx.ext.autosummary`,
  `sphinx.ext.napoleon` (Google/NumPy docstrings), `sphinx.ext.viewcode`,
  `sphinx_copybutton`, `sphinx_autodoc_typehints`.
- `html_theme = "furo"`.
- `sys.path.insert(0, os.path.abspath(".."))` so `utils` is importable.
- `autosummary_generate = True`.
- MyST: enable useful extensions (`colon_fence`, `deflist`, `linkify`).
- `autodoc_mock_imports`: **start empty**, run `sphinx-build` locally on
  Linux/WSL (or rely on the first RTD build), and add **only** the modules that
  actually fail to import there. Expected candidates: Windows-only imports
  pulled in by `utils/auto_vpn_win.py` / keyring's Windows backend (`winreg`,
  `win32cred`, `win32com`, ...). This is determined empirically, not guessed.

## 8. Content strategy — durable scaffold, loose sourcing

The README and the project are still evolving. Therefore:

- The **page structure** (section 4) is the contract; it is designed to be
  stable across project changes.
- Each page is **freshly written for the docs context**, using the current
  README as *source material* — not copied verbatim and not `{include}`-d from
  the README (which would break on badges, anchors, and relative links, and
  would couple the docs to a moving target).
- Where a topic is actively changing (e.g. the VPN tooling migrating to the
  `automatic-openconnect` repo), the page is a **short stub** that states the
  current status and links out, rather than duplicating volatile detail.
- The README itself is **not rewritten** by this task; at most it gains a
  "Full documentation: <rtd-url>" pointer (optional, confirm before editing).

## 9. Screenshot pipeline

A dev/docs-only tool: `tools/make_docs_screenshots.py`.

Behaviour:
1. **Credentials from the OS keyring** via `utils.secrets.get_secret(...)` —
   never hardcoded, never in config (consistent with the project's secret
   handling).
2. Launch Playwright (Chromium), log in, navigate to the target page
   (Termino booking list, uniCLOUD/Nextcloud web UI, etc.).
3. **Fail-safe blur before capture:** inject CSS (`page.add_style_tag`) that
   applies `filter: blur(...)` to PII-bearing regions. Blur **generously**
   (whole columns/regions), not by fragile precise selectors. If the expected
   DOM markers are absent, the tool **aborts** rather than capturing an
   un-blurred shot.
4. Save PNG to `docs/_static/screenshots/<name>.png`.
5. PNGs are **reviewed by a human and committed** via the normal workflow.
   RTD only embeds the finished PNGs.

A small declarative map drives it: `{ page_name -> (url, [blur_selectors], out_filename) }`.

### PII protection — defence in depth
1. Only project-relevant pages are captured.
2. Fail-safe blur applied **before** the screenshot is taken.
3. Tool aborts on DOM uncertainty (no silent un-blurred capture).
4. Human review at commit time.
5. RTD never has the credentials/VPN to reproduce a live capture.

## 10. Implementation phases (high level — detailed plan via writing-plans)

1. **Scaffold:** `.readthedocs.yaml`, `docs/conf.py`, `docs/index.md`, empty
   section dirs, `docs`/`screenshots` extras in `pyproject.toml`.
2. **Prose pages:** write the getting-started / usage / deployment /
   architecture / troubleshooting pages (durable, loosely sourced).
3. **API reference:** wire up `autosummary`, get a clean local Linux build,
   pin the minimal `autodoc_mock_imports`.
4. **Screenshot tool:** `tools/make_docs_screenshots.py` + blur map; generate
   and commit the first PNGs; embed them in the relevant pages.
5. **RTD activation:** connect the GitHub repo on readthedocs.org, verify the
   first cloud build is green (manual step on the user's side).

## 11. Verification plan

- Local: `uv run sphinx-build -b html docs docs/_build/html` must finish with
  **zero warnings treated as errors** (`-W` once stable), including a clean
  autodoc import on a Linux/WSL run.
- Existing test suite stays green: `python -m unittest discover -s tests`
  (the docs work must not touch runtime modules; the screenshot tool is
  isolated).
- RTD: first cloud build green; spot-check rendered nav, API pages, and that
  committed screenshots display with PII blurred.

## 12. Open questions / deferred to implementation

- Exact `autodoc_mock_imports` list — determined empirically at build time.
- Whether to add an RTD pointer to the README — confirm with user before
  editing the README (it is changing).
- RTD project slug (likely `semiautomatic-termino`) — set when connecting the
  repo (user-side step).
- Which specific screenshots are most useful — decided during phase 4 with the
  user, capturing only what aids comprehension.

## 13. Constraints honoured

- Nothing in uniCLOUD is modified or deleted (read-only navigation for shots).
- No secrets in code/config; keyring only.
- Windows-first dev workflow; commits go through `.\dev.ps1 commit` +
  `NEXT_COMMIT.md` (no direct `git` from the assistant).
- The daily runtime (`main.py`) is untouched; docs/screenshot tooling is
  strictly additive and optional.
