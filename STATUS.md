# Termino-Skript - aktueller Stand

**Stand:** 2026-05-28
**Lauffaehigkeit:** End-to-End gruen auf Windows (lokaler Entwickler-Rechner)
**Mail-Adresse:** Mails kommen jetzt von `your-mail@your-uni.at`
**Sheet-Quelle:** uniCLOUD (Nextcloud), Google nur noch als Fallback im Code
**Termino-Schreiben:** robust via JavaScript-Value-Assignment (Drupal-AJAX-tolerant)
**Kalender:** NoOp + CalDAV + EWS Sinks implementiert; config-default `type: "none"`
**Test-Suite:** 62 Unit-Tests passen (data_prep, mailing, calendar_sinks, calendar-hook)

---

## Architektur in einem Bild

```
┌────────────────────────────────────────────────────────────────┐
│ main.py                                                        │
│  ├── load_config / load_env_data / config_text                 │
│  ├── _resolve_mail_provider → make_sender(...)                 │
│  ├── TerminoSession (cookies, csv, antibot_key)                │
│  └── TaskRunner: idempotent daily tasks (status.json)          │
├────────────────────────────────────────────────────────────────┤
│ utils/                                                         │
│  ├── secrets.py          → python-keyring (Win Cred Mgr lokal, │
│  │                          CryptFile auf Linux-Server)        │
│  ├── mail_senders.py     → YahooSmtpSender, UniGrazEwsSender   │
│  ├── mailing.py          → first_message/reminder/vl_mail/...  │
│  │                         (provider-agnostisch via Sender)    │
│  ├── sheet_providers.py  → GoogleSheetProvider,                │
│  │                         UniCloudSheetProvider (WebDAV)      │
│  ├── unicloud.py         → schlanker WebDAV-Client             │
│  ├── extensions.py       → google_dp / data_prep (unverändert) │
│  ├── web_interaction.py  → Termino-Selenium                    │
│  │                         _set_input_via_js (NEU, robust)     │
│  │                         _highest_flagcollection_index (NEU) │
│  │                         new_appointment refactored          │
│  └── preperation.py      → load_env_data, config_text,         │
│                            load_session, ...                   │
├────────────────────────────────────────────────────────────────┤
│ tools/                                                         │
│  ├── migrate_env_to_keyring.py    (sensible.env → Keyring)     │
│  ├── create_unicloud_template.py  (Excel auf uniCLOUD anlegen) │
│  ├── update_unicloud_template.py  (mit fiktiven Daten füllen)  │
│  └── debug_termino_dom.py         (DOM-Dumper, war Diagnose)   │
├────────────────────────────────────────────────────────────────┤
│ Externe Abhängigkeiten:                                        │
│  • Cisco AnyConnect VPN (für EWS-Endpoint)                     │
│  • Chrome + ChromeDriver (Selenium für Termino)                │
│  • cloud.uni-graz.at:443 (uniCLOUD WebDAV, public)             │
│  • webmail.uni-graz.at:443/ews/exchange.asmx (nur via VPN)     │
│  • www.termino.gv.at (public)                                  │
└────────────────────────────────────────────────────────────────┘
```

---

## Credentials, die der Workflow braucht

Alle im **Windows Credential Manager** (lokal) bzw. **CryptFile-Keyring** (Server):

| Keyring-Key | Was | Risiko-Klasse |
|---|---|---|
| `termino-uni / termino-pw` | Passwort für termino.gv.at | mittel (scope: Termino) |
| `termino-uni / yahoo-app-pw` | Yahoo-App-Passwort (legacy fallback) | niedrig |
| `termino-uni / unicloud-app-pw` | Nextcloud-App-Passwort | mittel (scope: uniCLOUD) |
| `openconnect-sso / <email>` | **Uni-Login-Passwort** (EWS + VPN) | **HOCH** (voller Uni-Zugang) |
| `openconnect-sso / totp/<email>` | TOTP-Seed (nur Server, für headless VPN) | **HOCH** |

`sensible.env` enthält nur noch nicht-sensible Werte:
```
username_termino=Musikpsychologie
mail=your-mail@yahoo.com           # oder besser your-mail@your-uni.at
google_spreadsheet_url=...         # nicht mehr genutzt, bleibt als Backup
```

`config.json` enthält jetzt `mail_provider` und `sheet_provider`-Blöcke (Provider-Selektion).

---

## Was als Nächstes zu tun ist — Server-Deployment

`SERVER_HANDOFF.md` ist auf dem Stand vor Phase 3. Was noch dazu kommt fürs LXC-Setup:

1. **Zusätzliche Python-Pakete** (sind in `requirements.txt`):
   - `exchangelib>=5.6` (EWS)
   - `keyrings.cryptfile>=1.3` (headless keyring)
   - `pycryptodome` (transitiv)
   - `openpyxl>=3.1` (xlsx lesen/schreiben)

2. **Keyring auf Linux**: in der systemd-EnvironmentFile:
   ```
   PYTHON_KEYRING_BACKEND=keyrings.cryptfile.cryptfile.CryptFileKeyring
   KEYRING_CRYPTFILE_PASSWORD=<server-master-passphrase>
   ```

3. **Cisco VPN** (siehe SERVER_HANDOFF.md Abschnitt 5a) — openconnect-sso headless mit den Credentials aus dem Keyring.

4. **Chrome + Xvfb** für Selenium — bleibt wie geplant (siehe SERVER_HANDOFF.md Abschnitt 2).

5. **Provider-Configs auf dem Server**: `config.json` muss dort dieselben `mail_provider` und `sheet_provider`-Blöcke haben wie auf Davids Laptop. Wenn auf Linux, ist `unicloud-app-pw` über das CryptFile-Backend abrufbar.

---

## Offene Punkte / bekannte Schwächen

| Punkt | Schwere | Lösung |
|---|---|---|
| Termino-Bookings ohne Time-Werte (Edit-Modus "Nur Datum") werden vom Reader nicht erkannt | niedrig | Aktuell stand: Buchungsliste IS auf "Nur Datum" und Time-Inputs sind dennoch da — passt. Falls jemand "Nur Datum ohne Zeit" macht, wird der Slot übersprungen. |
| Selenium-Init mit ChromeDriverManager lädt bei jedem Lauf neuen Driver | sehr niedrig | Cache funktioniert, kein Problem. |
| Legacy-Code in `extensions.py` nach dem `return` ist tot | nur kosmetisch | Kann beim nächsten Cleanup entfernt werden. |
| Tests für `unicloud.py` und `sheet_providers.py` fehlen | mittel | Unit-Tests dafür schreiben (`tests/test_unicloud.py`, `tests/test_sheet_providers.py`). |
| Phase 4 (Kalender via CalDAV) noch nicht angegangen | bewusst zurückgestellt | Wenn gewünscht, eigene Phase mit `caldav`-Library. |

---

## Wenn morgen früh der Cron läuft (auf Davids Laptop)

Im Moment hast du **4 Termine in Termino** (3.06. und 10.06.2026) und **5 fiktive VLs** in der uniCLOUD-xlsx (TST1-5, alle mit deiner Uni-Mail). Da kein Termin auf morgen (28.05.) liegt, passiert beim nächsten manuellen `main.py`-Lauf **nichts** außer:
- Termino-CSV neu runterladen
- Phantom-Termine in Termino (falls noch welche da) löschen
- VL-Notifications-Pass läuft mit leerer Liste durch

Erst wenn ein Termin morgen wäre, würden die VLs eine Mail kriegen. Wenn du das aktiv testen willst: einen Eintrag in der xlsx für `28.05.2026` mit `TST1` setzen, dann läuft der ganze Pfad inkl. EWS-Mail an dich selbst durch.

---

## Cleanup nach dem Testen

Wenn du irgendwann sauber starten willst:
- Termino-Buchungsliste leeren (manuell in www.termino.gv.at, weil das Skript momentan nichts hat das nicht-Vergangenheit löscht)
- uniCLOUD-xlsx mit echten Daten ersetzen (jetzt fiktive TST1-TST5 drin)
- Im `update_unicloud_template.py` die `FICTIONAL_VLS` und `FICTIONAL_TIMETABLE` durch echte Daten ersetzen — ODER besser: direkt im Browser über Collabora editieren.
