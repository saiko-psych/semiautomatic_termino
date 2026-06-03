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
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
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
