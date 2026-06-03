# -*- coding: utf-8 -*-
"""Generate blurred web screenshots for the docs (dev/docs-only tool).

Captures project-relevant web pages (Termino, uniCLOUD/Nextcloud), blurring
all PII regions BEFORE the screenshot is taken. Fail-safe: if an expected
PII selector is not present on the page, we abort rather than risk an
un-blurred capture. Output PNGs go to docs/_static/screenshots/ and are
committed by a human after review. This tool never runs on the server or RTD.

Caveat: the guard only checks that each configured selector still matches at
least one element. It cannot tell whether a selector that still matches now
covers a *different* region (layout drift, a reused class name). The Task 8
human review of every PNG is the final backstop — never trust this guard alone.

Run:  uv run --extra screenshots python tools/make_docs_screenshots.py
      (requires `uv run playwright install chromium` once)
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass

# Make utils importable (for keyring-backed credentials in the live run).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# Conservative minimum blur radius. PII in dense tables can stay legible under
# light blur, so this is intentionally strong; the Task 8 human review is the
# final check. Bump it higher before lowering it.
BLUR_RADIUS = "16px"


class PIIGuardError(RuntimeError):
    """Raised when expected PII selectors are absent — we abort to stay safe."""


@dataclass
class ShotSpec:
    name: str
    url: str
    blur_selectors: list[str]
    out_filename: str
    extra_wait_selector: str = ""  # optional element to wait for before capture


def build_blur_css(selectors: list[str]) -> str:
    """CSS that heavily blurs every given selector (generous, fail-safe)."""
    joined = ", ".join(selectors)
    return f"{joined} {{ filter: blur({BLUR_RADIUS}) !important; }}"


def capture(spec: ShotSpec, page, out_dir: str) -> str:
    """Blur PII then screenshot. `page` is a Playwright Page (duck-typed).

    Aborts via PIIGuardError if no PII selectors are configured, or if any
    configured selector matches nothing, so we never capture a page whose PII
    layout we no longer recognise.
    """
    if not spec.blur_selectors:
        raise PIIGuardError(
            f"{spec.name}: no PII selectors configured; refusing to capture "
            f"(an empty selector list would blur nothing)"
        )
    missing = [sel for sel in spec.blur_selectors if page.locator(sel).count() == 0]
    if missing:
        raise PIIGuardError(
            f"{spec.name}: expected PII selectors not found {missing}; "
            f"aborting to avoid an un-blurred capture"
        )
    page.add_style_tag(content=build_blur_css(spec.blur_selectors))
    out_path = os.path.join(out_dir, spec.out_filename)
    page.screenshot(path=out_path, full_page=True)
    return out_path


# Termino auth reuse: the daily script logs into termino.gv.at (requests-based,
# see utils.web_interaction.termino_login) and caches the resulting Drupal
# session cookie as a flat {name: value} dict under "kekse" in session.json
# (see utils.preperation.session_json). We re-use that same cookie here instead
# of re-implementing the antibot/login flow. If session.json is absent or the
# cookie has expired, Termino redirects to its login page, which has none of the
# configured PII selectors -> the capture() guard aborts. So a stale session can
# never produce an un-blurred capture; it just fails loudly.
TERMINO_COOKIE_DOMAIN = ".termino.gv.at"


def termino_cookies_from_session(session_data) -> list[dict]:
    """Translate session.json's flat ``kekse`` dict into Playwright cookies.

    Returns ``[]`` when there are no cookies (missing/empty ``kekse``), so the
    caller can decide whether that is fatal for a given shot.
    """
    kekse = (session_data or {}).get("kekse") or {}
    return [
        {
            "name": name,
            "value": value,
            "domain": TERMINO_COOKIE_DOMAIN,
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax",
        }
        for name, value in kekse.items()
    ]


def load_termino_cookies(root: str) -> list[dict]:
    """Read ``session.json`` from the project root and return Playwright cookies.

    Returns ``[]`` if the file is missing or unparseable — for a Termino shot
    that means "run ``uv run python main.py`` first to create a logged-in
    session.json"; non-Termino shots are unaffected (cookies are domain-scoped).
    """
    path = os.path.join(root, "session.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return termino_cookies_from_session(json.load(f))
    except (FileNotFoundError, ValueError):
        return []


# Declarative capture map. Selectors are intentionally broad (whole columns).
# Fill in real selectors/URLs when capturing against the live sites.
SHOTS: list[ShotSpec] = []


def _run() -> None:  # pragma: no cover - needs a real browser + credentials
    from playwright.sync_api import sync_playwright  # lazy import

    out_dir = os.path.join(_ROOT, "docs", "_static", "screenshots")
    os.makedirs(out_dir, exist_ok=True)
    if not SHOTS:
        print("No ShotSpecs configured yet. Edit SHOTS in this file.")
        return
    cookies = load_termino_cookies(_ROOT)
    if cookies:
        print(f"reusing {len(cookies)} Termino session cookie(s) from session.json")
    else:
        print(
            "no Termino cookies in session.json - termino.gv.at pages will hit "
            "the login wall (the PII guard then aborts). Run "
            "`uv run python main.py` first to create a logged-in session.json."
        )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        if cookies:
            context.add_cookies(cookies)
        page = context.new_page()
        try:
            for spec in SHOTS:
                page.goto(spec.url)
                if spec.extra_wait_selector:
                    page.wait_for_selector(spec.extra_wait_selector)
                path = capture(spec, page, out_dir)
                print(f"saved {path}")
        finally:
            browser.close()


if __name__ == "__main__":  # pragma: no cover
    _run()
