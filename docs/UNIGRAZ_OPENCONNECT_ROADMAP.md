# Roadmap: `automatic-openconnect` standalone tool

> Status: PLANNING. No code in the new repo yet. Source of truth for
> the next Claude session — read this top to bottom before starting.

This document is the hand-off plan for spinning the Windows VPN
integration out of `termino_clean` into a standalone cross-platform
open-source tool. It exists so a fresh session has **all** the context
without the user having to re-explain.

---

## 0. tl;dr for the next session

User David has built a Windows VPN auto-setup module (`utils/auto_vpn_win.py`)
inside `termino_clean` (the music-psychology Termino automation). It is
production-grade and live-verified against Uni-Graz `univpn.uni-graz.at`.
There is also an older Linux version (`utils/auto_vpn.py`) that runs
on a Proxmox LXC server.

The user got **written approval from uniIT** (2026-06-02) to:
  - use openconnect as alternative VPN client (own risk)
  - store the TOTP seed in the OS keyring (own risk)
  - distribute the tool to other students and staff

The goal is to **extract the VPN logic into its own GitHub repo**
named `automatic-openconnect` (cross-platform: Windows, Linux, macOS),
host **docs on Read the Docs**, and **add a TOTP-hotkey daemon**
(Ctrl+Alt+P types the current TOTP code into whatever field has
focus). Termino then depends on this new repo as an optional
dependency.

This is roughly **20 hours of work** across **4-6 sessions**. Do not
try to do it all at once.

---

## 1. Context: what was built before this roadmap

### Tier 1 (merged to `main` of `saiko-psych/semiautomatic_termino`)
- `utils/auto_vpn_win.py` (~620 lines): Windows port of `auto_vpn.py`
- `utils/vpn_provider.py`: cross-platform factory
- `tests/test_auto_vpn_win.py`: 18 mocked tests
- `main.py`: 1-line factory swap

### Tier 2 Part A (`feat/setup-windows` branch, pushed)
- `tools/vpn-up.cmd`, `tools/vpn-down.cmd`, `tools/run-termino.cmd`:
  thin shims that elevate via UAC and call the corresponding Python.

### Tier 2 Part B (`feat/setup-windows` branch, pushed)
- `tools/setup-windows-tasks.ps1`: registers 3 Scheduled Tasks with
  "Run with highest privileges" + creates Desktop + Start Menu
  shortcuts. After one-time admin setup, double-click runs the
  task **silently elevated** without UAC.
- `tools/teardown-windows-tasks.ps1`: removes the tasks + shortcuts.

### Live-verified on David's laptop (2026-06-01 / 2026-06-02)
- openconnect.exe v9.12 (from openconnect-gui-1.6.2-win64)
- openconnect-sso 0.8.1 via `uv tool install --with PyQt6 --with "setuptools<70"`
- DOM-selectors `config.toml` at `~/.config/openconnect-sso/` (UTF-8 **without** BOM)
- TOTP seed + UGO password in Windows Credential Manager via `keyring` package
- Tunnel up in ~3 seconds, webmail.uni-graz.at reachable, full termino
  workflow runs end-to-end (55 seconds)
- Strg-C teardown clean, Cisco + Mullvad restarted

### Live-verified on CT 131 Proxmox LXC (2026-06-01)
- Linux openconnect-sso + xvfb-run + `keyrings.alt.file.PlaintextKeyring`
- 4 separate bugs found and fixed during that session (see
  `docs/AUTO-VPN-TEST-REPORT.md` in the server-management Cowork session
  — David has it locally, transcript of the fixes is in the
  `feat/auto-vpn-windows` PR commits 6236feb, d8ae846, b9ed354, 3904039)

---

## 2. uniIT approval (2026-06-02)

Verbatim quote from the response that matters for the licensing / docs:

> Aufgrund der Fülle an Software kann die uniIT nur jene Software
> unterstützen, die optimal mit dem VPN-Endpunkt zusammenarbeitet.
> OpenConnect können Sie auf eigenes Risiko und eigene Verantwortung im
> Rahmen der og Richtlinie verwenden. Bedauerlicherweise ist
> OpenConnect keine durch die uniIT unterstützte Software.

> [zur TOTP-Speicherung im Keyring] Aktuell gibt es kein Verbot zur
> Nutzung des Keyrings. Sie können das Secret im Rahmen der og
> Richtlinie auf eigenes Risiko bzw eigene Verantwortung im Keyring
> ablegen.

> [zur Weitergabe] Wie Sie den obigen Antworten bereits entnehmen
> können, lassen sich aus Ihrer Art der Softwareverwendung keine
> Verbote ableiten. Aufgrund der uns nicht bekannten Arbeitsumgebung
> und -methodik können wir keine Empfehlung zur von Ihnen
> beschriebenen Nutzung aussprechen.

Reference policy:
https://mitteilungsblatt.uni-graz.at/de/2007-08/31.a/pdf/

### What this means concretely for the new repo

- README.md, docs/index.md and the installer must carry a clear
  **"Use at your own risk. Not supported by uniIT."** banner.
- License must be permissive (MIT is fine, no copyleft concerns).
- The TOTP-storage page in the docs must recommend:
  - Disk encryption on (BitLocker / FileVault / LUKS)
  - A strong Windows / macOS / Linux login password
  - The TOTP feature is **opt-in** (default off in setup wizard)
- Repo is hosted under David's GitHub account (saiko-psych),
  **not** under any Uni-Graz organization. It is explicitly a
  community tool, not an institutional product.
- The Termino integration stays as it is — the new repo becomes an
  optional dependency.

---

## 3. Architecture of the new repo

```
automatic-openconnect/                  (GitHub, MIT license)
├── README.md                          (clear disclaimer + quick start)
├── LICENSE                            (MIT)
├── CHANGELOG.md
├── pyproject.toml                     (uv-managed, minimal deps)
├── .readthedocs.yaml                  (Read the Docs build config)
├── mkdocs.yml                         (mkdocs-material theme + nav)
├── .github/
│   ├── workflows/
│   │   └── tests.yml                  (matrix py3.10/3.11/3.13)
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── src/
│   └── automatic_openconnect/                   (Python package)
│       ├── __init__.py                (public API: auto_vpn_session, VPNError)
│       ├── core.py                    (shared base class / errors)
│       ├── _windows.py                (extracted from utils/auto_vpn_win.py)
│       ├── _linux.py                  (extracted from utils/auto_vpn.py)
│       ├── _macos.py                  (NEW - similar to _linux but no xvfb)
│       ├── factory.py                 (extracted from utils/vpn_provider.py)
│       ├── secrets.py                 (the openconnect-sso namespace bits
│                                       of utils/secrets.py)
│       ├── totp_typer.py              (NEW - hotkey-driven TOTP injector)
│       └── cli.py                     (CLI: up, down, status, totp-type,
│                                       totp-show, setup-* subcommands)
├── tools/
│   ├── setup-windows.ps1              (the big interactive bootstrapper -
│   │                                   sub of all the existing setup-* and
│   │                                   keyring-population steps; NEW)
│   ├── setup-windows-tasks.ps1        (existing, with paths re-pointed)
│   ├── teardown-windows-tasks.ps1     (existing)
│   ├── setup-linux.sh                 (NEW - apt/dnf/pacman packages,
│   │                                   uv tool install openconnect-sso,
│   │                                   keyring populate, systemd unit
│   │                                   template, vpn_up.sh/vpn_down.sh
│   │                                   from docs/SERVER_VPN_SETUP.md)
│   ├── setup-macos.sh                 (NEW - brew openconnect, uv tool ...)
│   ├── vpn-up.cmd / vpn-up.sh
│   ├── vpn-down.cmd / vpn-down.sh
│   └── totp-helper.cmd                (NEW - launches background hotkey daemon)
├── docs/                              (mkdocs-material source)
│   ├── index.md                       (landing page with disclaimer)
│   ├── installation/
│   │   ├── windows.md                 (screenshots: openconnect-gui installer,
│   │   │                               UAC prompt, setup-windows.ps1 run,
│   │   │                               Desktop shortcuts)
│   │   ├── linux.md
│   │   └── macos.md
│   ├── authenticator-setup.md         (THE most important user page -
│   │                                   how to extract the base32 seed
│   │                                   from Uni-Graz Keycloak's MFA setup,
│   │                                   which apps support it, what to do
│   │                                   if you're stuck with Microsoft
│   │                                   Authenticator)
│   ├── usage.md                       (vpn-up, vpn-down, totp-helper)
│   ├── totp-hotkey.md                 (how to enable Ctrl+Alt+P)
│   ├── troubleshooting.md             (the bug catalogue we built up)
│   ├── security.md                    (own-risk disclaimer, recommended
│   │                                   system hardening, what NOT to do)
│   ├── developer.md                   (how to contribute, test setup)
│   └── changelog.md                   (linked from CHANGELOG.md)
└── tests/
    ├── test_core.py
    ├── test_windows.py                (extracted from tests/test_auto_vpn_win.py)
    ├── test_linux.py                  (extracted from tests/test_auto_vpn.py)
    └── test_totp_typer.py             (NEW - mock keyboard + clock)
```

---

## 4. Phase plan

**Phase 0 - planning (this document) - DONE when commited**

**Phase 1 - new repo skeleton + code extraction** (~3h)
  1. Create GitHub repo `saiko-psych/automatic-openconnect`, public, MIT.
  2. `git init` locally, set up directory structure above (empty files
     where needed for now).
  3. Copy `utils/auto_vpn.py` -> `src/automatic_openconnect/_linux.py`.
  4. Copy `utils/auto_vpn_win.py` -> `src/automatic_openconnect/_windows.py`.
  5. Copy `utils/vpn_provider.py` -> `src/automatic_openconnect/factory.py`.
  6. Copy the openconnect-sso parts of `utils/secrets.py` ->
     `src/automatic_openconnect/secrets.py`. Strip out everything else
     (mail-PW, termino-PW, etc.).
  7. Adjust imports — every `from utils.X` becomes
     `from automatic_openconnect.X` or `from .X`.
  8. Write a minimal `__init__.py` that exposes `auto_vpn_session`
     (factory) and `VPNError`.
  9. `pyproject.toml` with python>=3.10, deps:
     - `keyring>=25.0`
     - `pyotp>=2.9`
     - `pynput>=1.7` (for the TOTP typer)
     - (no PyQt6 here — that's openconnect-sso's dep, installed
       separately via `uv tool install`)
  10. Copy `tests/test_auto_vpn.py` + `tests/test_auto_vpn_win.py`
      with adjusted imports. They should all stay green on Linux CI.
  11. Push first commit. Tag `v0.0.1`.

**Phase 2 - macOS port** (~2h)
  1. New `src/automatic_openconnect/_macos.py`. Pattern is closer to `_linux.py`
     than `_windows.py`:
     - No sudo on the user's behalf — caller must already be in a
       sudoers-enabled context, OR we shell out to `osascript -e
       'do shell script "..." with administrator privileges'` (which
       triggers a system password prompt, like a clicky UAC).
     - No Wintun, native utun adapter (openconnect handles it).
     - openconnect-sso works on macOS via the same PyQt6 mechanism.
  2. Add `_macos.py` import to `factory.py` with `sys.platform == "darwin"`.
  3. macOS-specific tests in `tests/test_macos.py`.

**Phase 3 - setup scripts for all 3 OS** (~3h)
  1. `tools/setup-windows.ps1`: end-to-end interactive wizard:
     - Check Python 3.10+ installed
     - Check uv installed (offer to install)
     - Check openconnect-gui installed (offer to download installer)
     - `uv tool install --with PyQt6 --with "setuptools<70" openconnect-sso`
     - Prompt for UGO email
     - Prompt for UGO password (masked) -> keyring
     - Prompt for TOTP base32 seed (validate format, show current code
       via pyotp, ask user to confirm against authenticator app) -> keyring
     - Write `config.toml` with UTF-8 no-BOM
     - Call existing `setup-windows-tasks.ps1`
     - Optional: register Ctrl+Alt+P hotkey via the totp-helper service
  2. `tools/setup-linux.sh`: bash wizard with `apt` / `pacman` /
     `dnf` detection. Lift code from `docs/SERVER_VPN_SETUP.md`.
  3. `tools/setup-macos.sh`: bash wizard with `brew openconnect`.

**Phase 4 - TOTP hotkey daemon** (~3h)
  1. `src/automatic_openconnect/totp_typer.py`:
     - Use `pynput.keyboard.GlobalHotKeys` for Ctrl+Alt+P registration
     - On hotkey: read TOTP seed from keyring, compute current 6-digit
       code via pyotp, type it with `pynput.keyboard.Controller`
     - Sit in a `while True` loop, log to stderr for debugging
  2. `automatic_openconnect.cli totp-helper start/stop`:
     - `start` writes a tiny pidfile, daemonizes (Windows: spawn a
       hidden powershell that runs python, drop a PID into
       `%APPDATA%\automatic-openconnect\totp-helper.pid`)
     - `stop` reads pidfile, kills
  3. Optional: tray-icon variant (`pystray` or platform-native) as a
     phase-4b add-on. Default mode is "headless background daemon".
  4. On Windows, install as a Scheduled Task with trigger "At log on"
     so it auto-starts. Provide `setup-totp-hotkey.ps1` for that.

**Phase 5 - Read the Docs** (~1h + ~5h documentation writing)
  1. `.readthedocs.yaml` with `mkdocs` builder, Python 3.11.
  2. `mkdocs.yml` with `mkdocs-material` theme.
  3. `requirements-docs.txt`.
  4. Connect Read the Docs to the GitHub repo (manual on readthedocs.org).
  5. Write `docs/index.md` with the security disclaimer.
  6. Write `docs/authenticator-setup.md` (THE crucial page —
     screenshots from David: Keycloak MFA setup, "Cannot scan?" link,
     base32 seed display, recommended apps Aegis/2FAS/Bitwarden, what
     to do if stuck on Microsoft/Google Authenticator).
  7. Write `docs/installation/{windows,linux,macos}.md`.
  8. Write `docs/usage.md`, `docs/totp-hotkey.md`, `docs/troubleshooting.md`,
     `docs/security.md`, `docs/developer.md`.

**Phase 6 - Termino integration** (~1h)
  1. In `termino_clean/pyproject.toml` add optional dep:
     ```toml
     [project.optional-dependencies]
     vpn = ["automatic-openconnect"]
     ```
     With install hint: `uv sync --extra vpn`.
  2. Replace `from utils.auto_vpn_win import auto_vpn_session_win`
     in `utils/vpn_provider.py` with
     `from automatic_openconnect import auto_vpn_session`.
  3. Delete the duplicated source: `utils/auto_vpn.py`,
     `utils/auto_vpn_win.py`, the openconnect-sso parts of
     `utils/secrets.py`.
  4. Update `tests/test_auto_vpn*.py` to test the integration not
     the implementation (or drop them — covered by the new repo's tests).
  5. Tag `termino_clean` `v2.1.0`, breaking change for users that
     used auto_vpn.

**Phase 7 - distribution test** (~2h)
  1. Find 1-2 willing colleagues with different setups (one Windows
     with no Cisco yet, one Linux Arch maybe).
  2. Send them only the Read the Docs URL + the setup script.
  3. Watch them install. Fix any sharp edges that come up.
  4. Iterate on the docs.

---

## 5. Decisions (locked in by David 2026-06-02)

1. **Repo name**: `automatic-openconnect`
2. **GitHub owner**: `saiko-psych` (David's personal account)
3. **License**: **MIT**
4. **PyPI publishing**: **NO — git-install only for now**. Distribute via
   `uv tool install --from git+https://github.com/saiko-psych/automatic-openconnect`.
   Rationale: small distribution (5-10 Uni-Graz colleagues directly),
   no need for PyPI namespace claim yet, zero maintenance overhead.
   Re-evaluate after ~20 users and a stable v1.0 API.
5. **TOTP-typer scope**: **minimal first** — global hotkey ->
   type 6-digit code at focused cursor. Tray-icon and multi-account
   support deferred to Phase 4b.
6. **Hotkey library**: **`pynput`**. If platform-specific issues
   come up (Windows accessibility-tools permissions, macOS
   Accessibility prompt), pivot to AutoHotkey on Windows / a
   tiny ObjC helper on macOS, but stay on pynput as long as it
   works.
7. **Default hotkey**: **Ctrl+Alt+P**. Make it configurable via
   the daemon's CLI flag for users who have it bound elsewhere.

### Implied repo URL
`https://github.com/saiko-psych/automatic-openconnect`

### Implied install command for end users
```
uv tool install --with PyQt6 --with "setuptools<70" \
    --from git+https://github.com/saiko-psych/automatic-openconnect \
    automatic-openconnect
```

(The two `--with` pins are inherited from the openconnect-sso dep —
see Lesson #2 in §6.)

---

## 6. Lessons learned that MUST flow into the new repo

### Bugs / quirks David and Claude found the hard way

1. **PowerShell `Set-Content -Encoding UTF8` writes a BOM** that
   TOML parser rejects. Must use `.NET WriteAllText` with
   `UTF8Encoding $false` for `~/.config/openconnect-sso/config.toml`.
   Cost: 1 hour to track down.

2. **openconnect-sso 0.8.1 imports `pkg_resources`**, which was
   removed in setuptools 70+. `uv tool install --with "setuptools<70"`
   is non-negotiable. Cost: another hour.

3. **Qt-WebEngine `--browser-display-mode hidden` crashes** on
   Windows with dedicated GPU (D3D errors). Use `shown` + DOM
   selectors in `config.toml` — with credentials in keyring it
   auto-fills in 2-3 seconds, functionally headless.

4. **openconnect-sso internally calls `sudo openconnect`** on
   Windows too. There is no Windows sudo by default (Win11 23H2
   has an opt-in one). Split: openconnect-sso `--authenticate`
   only (returns HOST/COOKIE/FINGERPRINT), then call
   `openconnect.exe` directly from already-elevated PowerShell.

5. **Wintun adapter creation needs Administrator**. No way around
   it — but Scheduled Tasks with "Run with highest privileges"
   bypass the UAC prompt after one-time admin setup.

6. **Cisco Secure Client + Mullvad VPN services compete with
   openconnect for routing**. Auto_vpn_win stops them temporarily
   (`net stop csc_vpnagent`, `net stop MullvadVPN`), restarts on exit.

7. **vpnc-script-win.js race**: openconnect prints "Configured
   as ..." as soon as CSTP is up, but the script then keeps running
   for 1-2 seconds to set DNS + routes. Wait for "Legacy IP route
   configuration done." instead, otherwise the first DNS lookup
   races and fails.

8. **Drain openconnect stdout in a background thread** after
   tunnel-up. Otherwise the OS pipe buffer fills (~64KB on Win) and
   openconnect blocks on next write, freezing the tunnel.

9. **`is_vpn_connected()` pre-flight TCP probe** races against
   adapter ordering on multi-VPN systems. When `auto_vpn` is
   enabled and brought the tunnel up successfully, **trust it** —
   don't re-probe at the end of the run.

10. **subprocess.run + text=True + Windows codepage cp1252** crashes
    on UTF-8 multibyte bytes. Always pass `encoding="utf-8",
    errors="replace"` on Windows.

11. **base32 TOTP secret validation**: A-Z + 2-7 only, case-insensitive,
    typical length 16/26/32 characters. Validate on entry — the user
    keyed in the 6-digit code once instead of the seed and we spent
    20 minutes on the resulting `binascii.Error: Non-base32 digit found`.

12. **DOM selectors for Uni-Graz Keycloak**:
    ```toml
    [[auto_fill_rules."https://login.uni-graz.at/*"]]
    selector = "input#username"
    fill = "username"
    # ... see existing config in tier-1 commits for the full list
    ```
    The MFA-app-selection step uses
    `selector = "label[for='31d086a8-3054-4551-b80c-35a07358d88d']"`
    — the UUID might be account-specific (David's account uses
    this UUID; other users may have a different one if they
    configured MFA at a different time). If auto-fill fails at
    the MFA-picker, document how to find the right UUID with
    browser devtools.

13. **Sudoers exact-arg matching** on Linux: `sudo /usr/bin/pkill
    -f <pattern>` is rejected by sudoers if the rule is bare
    `/usr/bin/pkill openconnect`. The Linux `_stop_tunnel` uses
    pgrep to find PIDs then `sudo /bin/kill <pid>` per PID, with
    `sudo /usr/bin/pkill openconnect` as failsafe.

14. **Service restart needs explicit stop-detection**:
    `_restart_services` should check `_service_status` first and only
    `net start` the ones that were `STOPPED`. Otherwise idempotency
    breaks for users who run vpn-down twice in a row.

### Authenticator app recommendations (from real pain)

- ✅ **Aegis** (Android, FOSS, F-Droid) — shows base32 seed any
  time via Edit → Show secret.
- ✅ **2FAS** (iOS + Android, FOSS) — same.
- ✅ **Bitwarden** (cross-platform) — TOTP feature shows seed.
- ✅ **1Password** — same.
- ⚠️ **Microsoft Authenticator** — convenient but the seed is
  one-way after setup. If the user already uses MS Authenticator,
  they must delete and re-add the MFA in Keycloak to get a fresh
  seed.
- ⚠️ **Google Authenticator** — same one-way story.

The setup wizard should validate the seed by computing the current
code and asking the user to confirm it matches their authenticator
app. That's how we caught David's wrong seed in the live session.

---

## 7. Files in `termino_clean` that need to be touched at extraction time

| File | Action |
|---|---|
| `utils/auto_vpn.py` | Copy to new repo as `_linux.py`, delete here once integration is done |
| `utils/auto_vpn_win.py` | Copy to new repo as `_windows.py`, delete here |
| `utils/vpn_provider.py` | Replace contents with `from automatic_openconnect import auto_vpn_session` shim, OR delete and import directly in main.py |
| `utils/secrets.py` | Extract openconnect-sso namespace bits to new repo's `secrets.py`. Keep the termino-PW / mail-PW namespaces here. |
| `tests/test_auto_vpn.py` | Move to new repo as `tests/test_linux.py` |
| `tests/test_auto_vpn_win.py` | Move to new repo as `tests/test_windows.py` |
| `tools/vpn-up.cmd`, `vpn-down.cmd`, `run-termino.cmd` | Update to call the new package: `python -m automatic_openconnect.cli up` etc. `run-termino.cmd` is termino-specific, stays here. |
| `tools/setup-windows-tasks.ps1`, `teardown-windows-tasks.ps1` | Move to new repo. The termino-specific bits (TerminoRun task) stay here. |
| `config.example.json` | Drop the `auto_vpn` section — that will be sourced from `automatic-openconnect`'s own config.json. Termino reads it via the lib. |
| `docs/SERVER_VPN_SETUP.md` | Move to new repo as `docs/installation/linux.md` (Linux server deployment guide, already well-written). |
| `CLAUDE.md` Backlog | Mark `automatic-openconnect`, `WINDOWS_SETUP.md`, macOS port, Read the Docs as "moved to new repo" once Phase 1 is done. |
| `NEXT_COMMIT.md` | Empty after each commit. |

---

## 8. The hotkey-TOTP-typer pseudocode

```python
# src/automatic_openconnect/totp_typer.py
import keyring
import pyotp
from pynput import keyboard

# Read config: which user's TOTP seed?
SERVICE = "openconnect-sso"   # same as openconnect-sso uses

def _get_seed(email: str) -> str | None:
    return keyring.get_password(SERVICE, f"totp/{email}")

def _on_hotkey(email: str) -> None:
    seed = _get_seed(email)
    if not seed:
        # Log to a file; popup might break the focused app's flow
        return
    code = pyotp.TOTP(seed).now()
    kc = keyboard.Controller()
    kc.type(code)

def run_daemon(email: str, hotkey: str = "<ctrl>+<alt>+p") -> None:
    """Blocking. Suggested to wrap in pythonw on Windows."""
    with keyboard.GlobalHotKeys({hotkey: lambda: _on_hotkey(email)}):
        keyboard.GlobalHotKeys({}).join()   # block forever
```

CLI wiring: `automatic-openconnect totp-helper start --email <e> --hotkey <h>`.
On Windows, install via `setup-totp-hotkey.ps1` which registers a
Scheduled Task with trigger "At log on of any user".

---

## 9. What to do at the start of the next Claude session

1. Read this file end-to-end. **Do not skim — every section has at
   least one thing you'd otherwise rediscover the hard way.**
2. Read `CLAUDE.md` in the same repo for the user's preferences.
3. Confirm with David: still want to do Phase 1 now? Any decisions
   from §5 changed?
4. Phase 1 needs about 3 hours of focused work. Don't start it if
   you can't complete it — partial extraction with broken imports
   is much worse than no extraction.
5. After Phase 1: tag the new repo `v0.0.1`, smoke-test
   `uv tool install --from git+...` on David's laptop, then move to
   Phase 2 or pause.

---

## 10. Risks / things that could derail this

- **The MFA-picker UUID is account-specific**. If David's
  `31d086a8-...` doesn't match another user's selector, auto-fill
  silently stops at the MFA-app picker. Mitigation: documentation
  page on how to find the UUID with browser devtools, plus a
  smart fallback in the selector (probably a `:contains("Authenticator")`
  selector if Qt-WebEngine's CSS engine supports it).

- **openconnect-gui v1.6.2 is from 2020 and stagnant**. It works
  but uses an old openconnect (v9.12 — actually decent, but the GUI
  installer is unsigned which makes Windows SmartScreen flag it).
  Long-term alternative: `winget install` the openconnect MSI
  from another source, or build openconnect-CLI separately. Document
  this in installation/windows.md as a known wart.

- **Microsoft Authenticator users will fight the setup**. They
  cannot extract the existing seed; they must reset MFA. Docs
  must explain this gently. We may end up writing a short FAQ
  entry called "I use Microsoft Authenticator, do I have to switch?"

- **macOS port is not free**. Apple Silicon openconnect builds
  exist (homebrew), but `sudo openconnect` on macOS triggers a
  GUI password prompt unless wrapped in `osascript`. There may
  be Wintun-style adapter weirdness too. We may discover that
  macOS needs its own session of debugging like we just did for
  Windows.

- **Read the Docs free tier limits**: 50 MB build size, 1 GB
  storage. Plenty for our use. Public docs only on free tier —
  fine, we want public anyway.

---

## 11. Quick start for the next session (commands)

```powershell
# Read this file
cat docs/UNIGRAZ_OPENCONNECT_ROADMAP.md

# Confirm decisions with David (Section 5)

# Phase 1: clone new repo skeleton
cd ..
git clone https://github.com/saiko-psych/automatic-openconnect
cd automatic-openconnect
# ... extract code per Section 4 Phase 1 ...
```

---

_Last updated: 2026-06-02. Maintained by Claude under David's direction._
_Live VPN-tunnel-up time on Windows: ~3 seconds. Live workflow time: 55 seconds._
_If you read this far, you have all the context you need to start._
