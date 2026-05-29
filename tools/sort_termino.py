# -*- coding: utf-8 -*-
"""
tools/sort_termino.py
=====================

Isolated test tool for the Termino chronological-sort logic.

Why this exists
---------------
The full main.py daily workflow is overkill when you only want to verify
that the sort-pass works. This script does only:

  1. Login to Termino (via session.json cached cookies)
  2. Navigate to the booking-list edit page
  3. Click "numbers" button to expose weight selects
  4. Run _sort_slots_chronologically (the SAME function main.py uses)
  5. Save

Or with --unsort:

  1+2+3 same
  4. Set RANDOM weights so the slots end up in random order
  5. Save

This lets you reproduce the sort test cycle in seconds without spawning
the whole workflow:

    python tools/sort_termino.py --unsort     # mess up the order
    python tools/sort_termino.py              # sort + verify

Run from the project root.
"""

from __future__ import annotations

import json
import sys
import time
import random
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.preperation import load_env_data, load_config, load_session
from utils.secrets import get_secret
from utils.web_interaction import (
    session as new_requests_session,
    termino_login,
    termino_antibot_key,
    bookinglist_url,
    get_buchungsliste_nummer,
    _sort_slots_chronologically,
)

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def _check_session_alive(cookies: dict, editing_url: str) -> bool:
    """Quick test: do the cached cookies still grant us the edit page?"""
    import requests
    if not cookies or not editing_url:
        return False
    try:
        r = requests.get(editing_url, cookies=cookies, allow_redirects=False, timeout=8)
        # If redirected to /user/login or status 302/403, session is dead.
        if r.status_code == 200 and "edit-field-flagcollection" in r.text:
            return True
    except Exception as e:
        print(f"  ! session check failed: {e}")
    return False


def _build_editing_url() -> tuple[str, dict]:
    """Try cached session.json first; only do full login if it failed.

    Saves ~10 seconds per call by skipping the Selenium antibot_key fetch
    and the actual login round-trip when the prior session is still good.
    """
    env_data = load_env_data()
    config_data = load_config()

    # --- attempt cached session ---
    try:
        (antibot, cookies, logged_url, booking_no, _csv) = load_session()
        if cookies and booking_no:
            editing_url = f"https://www.termino.gv.at/meet/de/node/{booking_no}/edit"
            if _check_session_alive(cookies, editing_url):
                print("[OK] Re-using cached session (no re-login needed)")
                return editing_url, cookies
            print("  ! Cached session expired or invalid; doing full login")
    except Exception as e:
        print(f"  ! Could not load cached session ({e}); doing full login")

    # --- full login fallback ---
    pw = get_secret("termino-pw")
    if not pw:
        print("[FAIL] termino-pw not in keyring")
        sys.exit(1)
    env_data["password_termino"] = pw

    sid = new_requests_session()
    antibot = termino_antibot_key()
    logged_url, cookies = termino_login(env_data, antibot, sid)
    booking_url = bookinglist_url(sid, logged_url)
    booking_no = get_buchungsliste_nummer(sid, booking_url, config_data)
    editing_url = f"https://www.termino.gv.at/meet/de/node/{booking_no}/edit"
    return editing_url, cookies


def _unsort_via_js(driver) -> int:
    """Set RANDOM weights to scramble the slot order. Returns count."""
    unsort_js = r"""
    return (() => {
        const sels = document.querySelectorAll(
            'select[id^="edit-field-flagcollection-und-"][id$="-weight"]'
        );
        // Discover weight range
        let minW = -10, maxW = 10;
        if (sels.length > 0 && sels[0].options.length > 0) {
            const vals = [];
            for (let i = 0; i < sels[0].options.length; i++) {
                const v = parseInt(sels[0].options[i].value);
                if (!isNaN(v)) vals.push(v);
            }
            if (vals.length > 0) {
                minW = Math.min.apply(null, vals);
                maxW = Math.max.apply(null, vals);
            }
        }
        // Shuffle weights in available range
        const range = maxW - minW + 1;
        const used = new Set();
        const out = [];
        sels.forEach(function(sel) {
            let w;
            do { w = minW + Math.floor(Math.random() * range); }
            while (used.has(w) && used.size < range);
            used.add(w);
            sel.value = String(w);
            sel.dispatchEvent(new Event('input',  {bubbles: true}));
            sel.dispatchEvent(new Event('change', {bubbles: true}));
            out.push(sel.id + ' -> w=' + w);
        });
        return JSON.stringify({count: out.length, updates: out});
    })();
    """
    try:
        result = driver.execute_script(unsort_js)
        parsed = json.loads(result) if isinstance(result, str) else result
        n = int(parsed.get("count", 0))
        print(f"  -> Unsort: {n} slots set to random weights")
        for u in (parsed.get("updates") or [])[:6]:
            print(f"     {u}")
        return n
    except Exception as e:
        print(f"  ! Unsort failed: {e}")
        return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--unsort", action="store_true",
                   help="set random weights (mess up the order) instead of sorting")
    args = p.parse_args()

    print("=" * 60)
    print(" sort_termino.py - isolated sort/unsort test")
    print("=" * 60)

    editing_url, cookies = _build_editing_url()
    print(f"Editing URL: {editing_url}")

    options = Options()
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(editing_url)
        time.sleep(2)
        for k, v in cookies.items():
            driver.add_cookie({
                "name": k, "value": v,
                "domain": ".termino.gv.at", "path": "/",
            })
        driver.refresh()
        time.sleep(3)

        # Expose weight selects
        try:
            btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    'a[title="Zeilen mittels numerischer Gewichtung ordnen statt mit Drag-and-Drop"]'
                ))
            )
            btn.click()
            print("numbers_button clicked")
            time.sleep(2)
        except Exception as e:
            print(f"numbers_button click failed: {e}")

        if args.unsort:
            n = _unsort_via_js(driver)
            label = "unsorted"
        else:
            n = _sort_slots_chronologically(driver)
            label = "sorted"

        if n > 0:
            try:
                save = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "edit-submit"))
                )
                save.click()
                print(f"Save clicked ({label} {n} slots)")
                time.sleep(4)
            except Exception as e:
                print(f"Save failed: {e}")
                return 1
        else:
            print(f"  ! {label.title()}: 0 slots - nothing saved")
            return 1

        print()
        print(f"[OK] Termino slots {label} ({n}).")
        print("    Open https://www.termino.gv.at/meet/de/b/.../406545 to verify.")
        return 0
    finally:
        try: driver.quit()
        except: pass


if __name__ == "__main__":
    sys.exit(main())
