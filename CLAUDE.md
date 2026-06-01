# CLAUDE.md - Termino-Skript Arbeitsanweisungen

Du arbeitest am `termino_clean`-Skript für die Musikpsychologie-Studie der Uni Graz. Dieses Dokument ist der Vertrag mit dem User. Lies es vor jedem Refactor.

## Was das Skript ist

Tägliches Automation-Skript: liest die VL-Zuteilungen aus einer xlsx in uniCLOUD, synchronisiert mit termino.gv.at (Buchungsplattform), schickt Bestätigungs/Erinnerungs-Mails an Probandinnen und Versuchsleiter, und (optional) legt Kalender-Events an.

End-Ziel: läuft idempotent als systemd-Timer auf einem Proxmox-LXC-Container, ohne dass irgendwer was tun muss.

## User-Anforderungen (HARD CONSTRAINTS - keine Ausnahmen)

1. **Kritisches Denken, kein Lobeshymn-Reflex.** Wenn der User sagt "X funktioniert", verifiziere es; nimm es nicht als wahr an. Wenn der User eine Lösung vorschlägt und sie ist falsch, sag ihm das.
2. **Erst recherchieren, dann lösen.** Niemals direkt eine Lösung raushauen. Lies den relevanten Code, verstehe das Datenmodell, dann fixe.
3. **Verifizieren, ob es tatsächlich funktioniert hat.** Unit-Tests sind nicht genug. End-to-End offline-Simulation ist Pflicht für jeden nicht-trivialen Fix - bauen + ausführen, nicht nur "die Tests laufen".
4. **NICHTS in uniCLOUD löschen.** Wirklich nichts. Backup-First, If-Match-Header, never blind overwrite.
5. **Mail-Adresse: `your-mail@your-uni.at`.** Yahoo ist nur Legacy-Fallback.
6. **Plattform: User arbeitet auf WINDOWS.** Python 3.13. Keine Linux-Befehle ohne Rückfrage. PowerShell-Skripte für Anweisungen.

## Architektur (Provider-Pattern, dreimal)

```
main.py
  -> _resolve_mail_provider(config.json)  -> MailSender   (Yahoo SMTP | Uni-Graz EWS)
  -> make_sheet_provider(config.json)      -> SheetProvider (Google | uniCLOUD WebDAV)
  -> make_calendar_sink(config.json)       -> CalendarSink  (NoOp | CalDAV | EWS)
```

Jeder Provider ist ABC mit `.send()` / `.fetch()` / `.upsert_event()`, gebaut über Factory-Funktion. Secrets kommen aus `utils.secrets.get_secret(name)` (python-keyring auf Windows Credential Manager bzw CryptFile-Keyring auf Linux). Niemals Passwörter in env/config.

## Kritische Dateien

| Datei | Verantwortlich |
|---|---|
| `main.py` | Orchestrator. TaskRunner + status.json (idempotent: jede Task einmal pro Tag) |
| `utils/secrets.py` | python-keyring-Wrapper, CLI `set/get/delete/list` |
| `utils/mail_senders.py` | `YahooSmtpSender`, `UniGrazEwsSender` (exchangelib + Basic Auth) |
| `utils/mailing.py` | `first_message` / `reminder` / `vl_mail` / `termin_missing` (alle defensiv) |
| `utils/sheet_providers.py` | `GoogleSheetProvider`, `UniCloudSheetProvider` + `_serialize_cell` |
| `utils/calendar_sinks.py` | `NoOpCalendarSink`, `UniCloudCalDAVSink`, `ExchangeEWSSink` + `push_slots_to_calendar` |
| `utils/extensions.py` | `google_dp`, `data_prep`, `data_prep_2` - Spreadsheet↔Termino-Diff |
| `utils/web_interaction.py` | Selenium gegen termino.gv.at. `_set_input_via_js`, `_highest_flagcollection_index`, `new_appointment` |
| `utils/preperation.py` | `load_env_data`, `load_config`, `config_text`, `tomorrow_today_data`, `get_ids_to_remove` |
| `utils/unicloud.py` | Eigener schlanker WebDAV-Client (PROPFIND/PUT/If-Match) |
| `status.json` / `session.json` | Runtime-State, NIE committen (in .gitignore) |
| `config.json` | Provider-Auswahl + Studien-Metadaten |
| `tests/` | 90 Unit-Tests, alle offline, `python -m unittest discover -s tests` |

## Gotchas, die uns schon einmal verbrannt haben

### Filesystem / Tooling

- **Edit-Tool truncated mehrfach Dateien**. Verwende ausschließlich `cat > / cat >>` via Bash für Änderungen an Dateien > 100 Zeilen. Nach JEDER Änderung: `python -c "import ast; ast.parse(open(F).read())"` + `wc -l` zur Verifikation.
- **`.pyc` ist klebrig**. Wenn nach einem Edit ein Symbol "fehlt", erstmal `__pycache__/` checken bzw. clean Reload via `importlib.reload`.
- **Git-Init darf NICHT im Sandbox-Mount.** Nur in PowerShell auf User-Seite. Setup-Skript: `git_setup.ps1`.

### openpyxl / xlsx / Collabora

- **Excel "Time"-Zellen kommen als `datetime(1900,1,1,H,M)`** durch openpyxl. `_serialize_cell` muss typ-bewusst sein: `datetime.time`→`HH:MM`, `datetime` mit year≤1900→`HH:MM`, sonst `DD.MM.YYYY` bzw. `DD.MM.YYYY HH:MM`.
- **Collabora-Datum**: User muss `'29.05.2026` (mit führendem Apostroph) eintippen, sonst macht der Sheet-Editor was Komisches. Apostroph wird vom openpyxl-Reader gestrippt.
- **`'01.01.1900'` String im CSV** = Phantom-Wert eines kaputten Time-Cells. `_is_valid_uhrzeit` erkennt und filtert.
- **VL-Zelle ohne Datum/Uhrzeit** = Phantom-Row. Pandas `ffill` propagiert das Datum, aber Uhrzeit bleibt NaN. `data_prep` / `google_dp` müssen das filtern.

### Pandas

- **`df[empty_object_series]` verliert alle Spalten.** Mask immer `.astype(bool)` und `if not df.empty:` voranstellen.
- **`pd.to_datetime(..., errors='coerce')` ist Pflicht** an jeder Stelle die User-Daten konvertiert. Sonst killt ein bad value den ganzen Daily-Run.
- **Nach `ffill` kann NaT trotzdem da sein** (wenn die Spalte oben leer ist). Immer `df = df[df["X"].notna()].copy()` direkt danach.

### Termino / Selenium / Drupal-AJAX

- **JS `.click()` triggert Drupal-AJAX nicht.** Echte WebDriverWait + element_to_be_clickable + `.click()` nutzen.
- **Date/Time inputs: JS-Value-Assignment + dispatchEvent('input','change','blur')**, nicht send_keys. Termino hat KEINE jQuery-Datepicker, sondern plain text inputs.
- **Slot-IDs sind unpredictable `und-N`**. `_highest_flagcollection_index` scannt DOM live.
- **`split('-')[4]`** ist fragil. Immer Bounds-Check oder Token-Scan-Fallback (`_extract_index`).

### EWS / Mail / VPN

- **EWS-Endpoint `webmail.uni-graz.at`** ist nur via Cisco VPN erreichbar. Ohne VPN kein Versand.
- **Keycloak-Mail-Passwort funktioniert NICHT.** EWS will das normale Uni-Login-PW.
- **`config_text`** zeigt aktiven Provider, nicht Yahoo-Legacy. Nie wieder `Yahoo-App-Passwort` printen wenn EWS aktiv.

### Idempotenz

- **`status.json`** hält pro Tag fest welche Tasks gelaufen sind. Vor manuellem Test: `Remove-Item status.json`.
- **`session.json`** cached Termino-Login. Wird automatisch erneuert bei Bedarf.
- **Calendar-Sinks** sind idempotent über stabile SHA1-UID aus `study_name|slot_time|datetime`. CalDAV: PUT auf gleiche UID = update. EWS: find-by-marker + delete + save.

## Workflow für Code-Änderungen

1. `git status` + `git diff` lesen, was schon offen ist
2. Den User briefen, **was du vorhast und warum**, BEVOR du editierst
3. Bei Dateien > 100 Zeilen: cat-Heredoc, nicht Edit
4. Nach jedem Schreib-Vorgang: AST-Parse + `wc -l` Verifikation
5. Unit-Tests: `python -m unittest discover -s tests` muss grün bleiben
6. End-to-End-Simulation für kritische Pfade (synthetisches xlsx → CSV → data_prep → mailing → calendar)
7. Commit nach jedem grünen Block: `git add -A; git commit -m "..."`
8. **Niemals** behaupten "alles funktioniert" ohne den tatsächlichen Pipeline-Lauf gesehen zu haben

## Git-Workflow (INTEGRIERT - keine manuellen Schritte fuer den User)

Nach JEDEM Code-Aenderungs-Block musst du:

1. **Tests laufen**: `python -m unittest discover -s tests` muss gruen sein. Wenn nicht: erst fixen.
2. **NEXT_COMMIT.md aktualisieren** mit einer 1-3 Zeilen Zusammenfassung der Aenderung. Format:
   ```
   <typ>: <kurze beschreibung>

   - Was hat sich geaendert / warum
   - Welche Files
   ```
   Typ ist eines von: fix, feat, refactor, test, docs, chore.
3. Den User informieren: "Commit ist bereit - lass `.\dev.ps1 commit` laufen".

Der User tippt dann EINEN Befehl in PowerShell: `.\dev.ps1 commit`. Das Skript:
- Zeigt status + diff
- Laeuft Tests (Abbruch wenn rot)
- Liest NEXT_COMMIT.md fuer die Message
- Committed
- Leert NEXT_COMMIT.md

Der User soll NICHT manuell `git add` / `git commit` tippen muessen.

Wenn du selber `git`-Operationen aus der Sandbox versuchst, **werden sie nicht zuverlaessig funktionieren** - der virtiofs-Mount blockiert `.git/`-Schreibops. Also: NUR Files im Projekt anlegen/aendern + NEXT_COMMIT.md fuellen. Nichts mit `.git/` versuchen.

## Was definitiv NICHT funktioniert ist (Stand 2026-05-28)

- **Calendar-Sinks live**: nur in Tests gegen Mocks getestet, nicht gegen echte uniCLOUD-CalDAV bzw. Outlook-EWS
- **Server-Deployment auf LXC**: geplant, nicht durchgeführt
- **Phase 4 Kalender Live-Test**: User muss `calendar_provider.type` auf `unicloud-caldav` oder `uni-graz-ews` setzen und manuell verifizieren

## Geverifiziert (Stand 2026-05-28)

- 90 Unit-Tests grün
- End-to-End offline-Simulation mit künstlich kaputter xlsx (01.01.1900-Glitch + Phantom-Row): defensive Filter funktionieren, keine Crashes
- EWS-Mail-Versand wurde vom User in einem früheren Lauf erfolgreich getestet
- Termino-Selenium: 4 echte Appointments wurden vom User-Lauf korrekt eingetragen
- uniCLOUD-WebDAV: User hat erfolgreich Excel-Datei hin und her geschrieben

## Offene User-Wuensche (Backlog)

- **Config-UI**: User will config.json-Aenderungen einfach machen koennen, idealerweise per GUI. Provider-Switches (mail/sheet/calendar), Keyring-Secrets, Pfade. Erste Stufe: interaktives PowerShell-Skript `.\config.ps1`. Spaetere Stufe: kleines Tkinter-Fenster oder lokale HTML-Page. Bei Aenderungen an config.json / utils/secrets.py daran denken dass dort spaeter ein UI ansetzen wird.
- **Read the Docs**: User-Wunsch (2026-06-01) das Projekt auf readthedocs.io zu hosten. Vermutlich mkdocs-material oder Sphinx, mit den existing .md-Files (README, SERVER_VPN_SETUP, WINDOWS_SETUP wenn da, etc.) als Quelle. Auch ein `.readthedocs.yaml` braucht's. Nicht dringend, aber waere schoen fuer Distribution.
- **docs/WINDOWS_SETUP.md**: User-facing Setup-Guide fuer Windows-Auto-VPN-Integration (Voraussetzung fuer 5-10 Non-IT-User-Distribution). Mit Screenshots: openconnect-gui installieren, uv installieren, openconnect-sso via uv tool, config.toml setzen, Keyring fuellen via setup-windows.ps1.
- **tools/setup-windows.ps1**: interaktiver Bootstrapper fuer obigen Setup. Macht alle Pfade automatisch, validiert TOTP-Seed mit Vergleich gegen Authenticator-App, legt Desktop-Verknuepfung mit Admin-Flag an.
- **macOS auto_vpn**: utils/auto_vpn_mac.py - aktuell ist macOS no-op in utils/vpn_provider.py. Cisco Secure Client auf macOS hat aehnliche SAML-Limits wie auf Windows. openconnect-sso laeuft prinzipiell auch auf macOS (homebrew openconnect + uv tool openconnect-sso), nur ohne der Wintun/sudo-Spezialitaeten. Wird Pfad B sein wenn jemand das brauchen sollte.

## Wenn etwas crasht

Dem User folgendes geben:
1. Den exakten Traceback abfragen
2. NICHT spekulieren - die fehlerverursachende Zeile lesen, dann ENTLANG des Datenflusses rückwärts
3. Wenn Edit-Tool wieder truncated: per `cat >>` rekonstruieren, nicht nochmal Edit
4. Bei einer Vermutung: erst Hypothese verifizieren (mit `python -c "..."` reproduzieren), dann fixen

