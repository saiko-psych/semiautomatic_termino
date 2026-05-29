# Testing - termino_clean

**Stand: 2026-05-28** -- 90 Unit-Tests, alle gruen auf Python 3.13 / Windows 11.

```powershell
.\dev.ps1 test              # alle Tests verbose
python -m unittest discover -s tests
```

---

## Was getestet ist

### Unit-Tests (90 Tests, 7 Files, ~0.5s)

| File | Tests | Was es verifiziert |
|---|---|---|
| `test_calendar_sinks.py` | 19 | CalendarEvent UID-Stabilitaet; NoOp/CalDAV/EWS Idempotenz; make_calendar_sink Factory (`none`/`unicloud-caldav`/`uni-graz-ews`); CalDAV update vs. neu erstellen; EWS find-by-marker delete-then-save |
| `test_data_prep.py` | 10 | data_prep diff_termino (VL fehlt vs. orphan); data_prep_2 (neue Termine); get_ids_to_remove (Vergangenheit, Heute, Morgen-mit/ohne-Slot, Zukunft) |
| `test_defensive_fixes.py` | 10 | first_message/reminder/vl_mail skippen NaN-Termin, NaN-mail, NaN-time mit Warning; data_prep crashed nicht bei leerer Datum-Spalte; google_dp warnt bei VL-Kuerzel das nicht im info-sheet ist |
| `test_mail_senders.py` | 18 | YahooSmtpSender + UniGrazEwsSender Connection-Reuse, Plain/HTML, From-Override; make_sender Factory; Fehler bei missing username/secret |
| `test_mailing.py` | 9 | first_message Template-Substitution; reminder Subject-Format; vl_mail mit/ohne Teilnehmer; termin_missing Alert-Body |
| `test_main_calendar_hook.py` | 6 | push_slots_to_calendar: ein Event pro Slot (nicht pro VL), distinkte Slots, Idempotenz, malformed time skipped, Sink-Error abort-resilient |
| `test_xlsx_pipeline_fixes.py` | 18 | _serialize_cell type-aware (datetime.time, 1900-glitch, real-date); _is_valid_uhrzeit/normalize; data_prep mit phantom-row + Collabora-format |

### End-to-End Offline-Simulation

Manuell verifiziert mit einer synthetisch zusammengebauten xlsx, die **alle bekannten Bug-Pattern auf einmal enthaelt**:

- Excel time-of-day als `datetime(1900,1,1,H,M)` (Collabora)
- Phantom-Row (VL gesetzt, keine Uhrzeit, kein Datum)
- Garbage time string (`'NOPE'`)
- VL-Kuerzel das im information-Sheet fehlt
- VL mit leerer Mail-Adresse
- forward-fill Datum ueber mehrere Uhrzeit-Zeilen
- Mix valider und invalider Zeilen

**Ergebnis:**
- 0 Crashes
- 3 valide VL-Mails (statt 0 mit altem Code, oder Crash)
- 2 Kalender-Events
- Idempotenz: zweiter Lauf produziert keine Duplikate

### Bestaetigte echte Pipeline-Schritte (vom User durchgefuehrt)

- EWS-Mail-Versand `your-mail@your-uni.at` -> Inbox (frueherer Lauf, Mail kam an)
- Termino-Selenium: 4 Appointments korrekt eingetragen (3., 10.06.2026 Slots)
- uniCLOUD-WebDAV: Excel-Datei hin und her geschrieben

---

## Was NICHT getestet ist

### Live-Tests gegen echte Server (kein Mock)

| Komponente | Status | Was fehlt |
|---|---|---|
| **UniCloudCalDAVSink (live)** | nicht getestet | Echte CalDAV-Request an cloud.uni-graz.at; iCalendar-Roundtrip; Discovery von principal/calendars |
| **ExchangeEWSSink Kalender (live)** | nicht getestet | Echte EWS CalendarItem.save() Roundtrip; ExtendedProperty Marker-Suche |
| **VL-Reminder-Pipeline (live)** | nicht getestet | xlsx-Eintrag fuer morgen -> echte EWS-Mail an VL kommt an |
| **insert_new_app_in_termino (live)** | seit Refactor nicht | Neue _extract_index Token-Scan-Fallback bei kaputtem Button-ID |

### Edge-Cases die wir noch nicht abdecken

- Mehr als 4 VLs pro Slot (VL1..VL4 ist hart kodiert)
- Termino-Bookings mit Datum **vor** 1970 (pandas-Bereich)
- xlsx mit > 100 Zeilen (Performance-Profil unbekannt)
- VPN-Disconnect mitten im EWS-send (was passiert? Retry?)
- WebDAV-Server gibt 5xx (UniCloudClient.upload-Retry-Verhalten)

### Was Unit-Tests grundsaetzlich nicht abdecken

- Race conditions zwischen `status.json` Write + zweiten Daily-Lauf
- Chrome/Selenium Timing (verstaendnis aus echtem Lauf, nicht aus Test)
- VPN/openconnect-sso Auth-Flow (TOTP, Token-Refresh)
- Keyring-Backend-Switch zwischen Windows-Credential-Manager (lokal) und CryptFile (Server-LXC)

---

## Wie man neue Tests schreibt

Pattern: jede neue Funktion soll mindestens **3 Tests** haben:

1. **Happy Path:** Ein typischer Eingabe-Set, Output stimmt
2. **Edge Case:** Leere Liste, NaN, leerer String, fehlende Optional-Felder
3. **Failure-resilience:** Mock von externer Abhaengigkeit wirft Exception -> Code crashed nicht

Konvention fuer Test-Helper:
```python
class _Spy:
    def __init__(self): self.sent = []
    def send(self, m): self.sent.append(m)
    def close(self): pass


@mock.patch("utils.mailing._human_pause", lambda *a, **kw: None)
class TestMyFunction(unittest.TestCase):
    def test_happy(self): ...
    def test_empty_input(self): ...
    def test_send_failure_does_not_abort(self): ...
```

---

## Bekannte Test-Anomalien

- **UserWarning: "Could not infer format"** in test_garbage_datum_string_is_skipped - kommt aus pandas wenn ein bad-date String drin ist. Harmless, der Code droppt die Zeile danach. Wir koennten das mit `warnings.catch_warnings()` unterdruecken, aber der Output ist eine sinnvolle Diagnose-Info wenn ein User das Skript laufen laesst.

- **2x Hilfs-Print "data_prep: 2 Zeile(n)..."** waehrend Tests laufen - kein Bug, das ist die Skript-Diagnose-Ausgabe die im Real-Lauf hilfreich ist.

---

## Wie man Tests laeuft (Performance)

```powershell
# Alle Tests, leise (nur Endsumme)
python -m unittest discover -s tests

# Verbose (zeigt jeden Test-Namen)
python -m unittest discover -s tests -v

# Nur ein File
python -m unittest tests.test_calendar_sinks

# Nur eine Klasse
python -m unittest tests.test_mailing.TestVlMail

# Nur ein einzelner Test
python -m unittest tests.test_mailing.TestVlMail.test_send_failure_does_not_abort_batch
```

Typische Laufzeit: **~0.5 Sekunden** fuer alle 90 Tests.
