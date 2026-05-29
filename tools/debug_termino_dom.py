# -*- coding: utf-8 -*-
"""
tools/debug_termino_dom.py
==========================

Diagnostic script for the Termino "insert new appointment" failure.

What it does
------------
1) Logs into Termino with your credentials (from the keyring).
2) Opens the booking-list edit page.
3) Captures a screenshot + a JSON dump of all <input> IDs BEFORE any click.
4) Clicks the "More" button ONCE.
5) Waits 3 seconds for the DOM to update.
6) Captures another screenshot + JSON dump AFTER the click.
7) Diffs the two: which input IDs are NEW after the More-click?

The output goes to ./debug_termino/. Send me those files and I'll fix
new_appointment() with the real ID pattern, not the guessed one.

Run:
    python tools/debug_termino_dom.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.preperation import load_env_data, load_config
from utils.secrets import get_secret
from utils.web_interaction import (
    session as new_requests_session,
    termino_login,
    termino_antibot_key,
    bookinglist_url,
    get_buchungsliste_nummer,
)

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


OUTDIR = Path("debug_termino")


def dump_inputs(driver) -> list:
    """Return list of {id, name, type, value, visible} for every <input>."""
    js = r"""
    return Array.from(document.querySelectorAll('input,select,button')).map(el => ({
      tag: el.tagName,
      id: el.id || null,
      name: el.name || null,
      type: el.type || null,
      value: el.value || null,
      visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
      placeholder: el.placeholder || null,
    }));
    """
    return driver.execute_script(js)


def main() -> int:
    OUTDIR.mkdir(exist_ok=True)
    print(f"Outputs go to: {OUTDIR.absolute()}")

    # ---- 1) Login ----
    env_data = load_env_data()
    config_data = load_config()
    pw = get_secret("termino-pw")
    if not pw:
        print("Termino password not in keyring."); return 1
    env_data["password_termino"] = pw

    print("Fetching antibot key + logging in to Termino...")
    sid = new_requests_session()
    antibot = termino_antibot_key()
    logged_url, cookies = termino_login(env_data, antibot, sid)
    booking_url = bookinglist_url(sid, logged_url)
    booking_no = get_buchungsliste_nummer(sid, booking_url, config_data)
    editing_url = f"https://www.termino.gv.at/meet/de/node/{booking_no}/edit"
    print(f"Editing URL: {editing_url}")

    # ---- 2) Open editor in Chrome with cookies ----
    options = Options()
    options.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(editing_url)
        time.sleep(2)
        for k, v in cookies.items():
            driver.add_cookie({"name": k, "value": v,
                               "domain": ".termino.gv.at", "path": "/"})
        driver.refresh()
        time.sleep(4)

        # ---- 3) Snapshot BEFORE ----
        before_inputs = dump_inputs(driver)
        (OUTDIR / "before_dump.json").write_text(
            json.dumps(before_inputs, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        driver.save_screenshot(str(OUTDIR / "before_more_click.png"))
        print(f"  before: {len(before_inputs)} elements dumped")

        # ---- 4) Click numerical-ordering button first (matches main flow) ----
        try:
            numeric_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    'a[title="Zeilen mittels numerischer Gewichtung ordnen statt mit Drag-and-Drop"]'
                ))
            )
            numeric_button.click()
            print("  numerical-ordering button clicked")
            time.sleep(2)
        except Exception as e:
            print(f"  numerical button not clicked: {e}")

        # ---- 5) Click "More" once ----
        try:
            more_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((
                    By.ID, "edit-field-flagcollection-und-add-more"
                ))
            )
            more_button.click()
            print("  More button clicked")
        except Exception as e:
            print(f"  More button click FAILED: {e}")

        # ---- 6) Wait for DOM update + snapshot AFTER ----
        time.sleep(3)
        after_inputs = dump_inputs(driver)
        (OUTDIR / "after_dump.json").write_text(
            json.dumps(after_inputs, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        driver.save_screenshot(str(OUTDIR / "after_more_click.png"))
        print(f"  after: {len(after_inputs)} elements dumped")

        # ---- 7) Compute diff ----
        before_ids = {el.get("id") for el in before_inputs if el.get("id")}
        after_ids = {el.get("id") for el in after_inputs if el.get("id")}
        new_ids = sorted(after_ids - before_ids)

        diff_report = {
            "before_count": len(before_inputs),
            "after_count": len(after_inputs),
            "new_element_ids_after_more_click": new_ids,
            "examples_of_new_elements_full_info": [
                el for el in after_inputs
                if el.get("id") in new_ids
            ],
        }
        (OUTDIR / "DIFF_REPORT.json").write_text(
            json.dumps(diff_report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print()
        print("=" * 60)
        print(f"  NEW element IDs after More-click: {len(new_ids)}")
        for nid in new_ids[:25]:
            print(f"    + {nid}")
        if len(new_ids) > 25:
            print(f"    ... and {len(new_ids)-25} more")
        print("=" * 60)
        print()
        print("Files written:")
        for f in sorted(OUTDIR.iterdir()):
            print(f"  {f}  ({f.stat().st_size} bytes)")
        print()
        print("Send me DIFF_REPORT.json (or all three JSON files) and I'll")
        print("rewrite new_appointment() to find the real inputs deterministically.")

        # ---- 8) Wait for user inspection ----
        input("Press Enter to close the browser when you're done inspecting...")

    finally:
        driver.quit()

    return 0


if __name__ == "__main__":
    sys.exit(main())
