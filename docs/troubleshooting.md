# Troubleshooting

## `Login failed, fetching new antibot key...` loops forever

Your Termino password has likely changed. Refresh it:

```bash
uv run python -m utils.secrets set --termino
```

## EWS raises `Could not resolve host`

The script cannot reach `webmail.uni-graz.at`. This host is only accessible through the Uni-Graz VPN. Connect via Cisco Secure Client (or the headless `openconnect-sso` path on a server) before running. See {doc}`deployment/vpn-setup`.

## `No module named 'caldav'` after `git pull`

A new dependency was added since your last sync. Re-run:

```bash
uv sync
```

## Selenium hangs on the "Mehr hinzufuegen" button

Termino is Drupal-AJAX-based and occasionally drops slot containers from the DOM mid-render. The Save-Reload-Sort-Save pattern in `utils/web_interaction.py` is designed to work around this. If the hang persists, reset with:

```bash
uv run python tools/sort_termino.py --unsort
```

Then retry the normal run.

## Excel cell `01.01.1900` appearing in CSV output

This is the openpyxl epoch glitch for time-only cells (openpyxl represents a bare time value as `datetime(1900, 1, 1, H, M)`). The filter in `_is_valid_uhrzeit` catches these and drops the row with a console warning rather than crashing. No action needed unless the warning appears for rows that should be valid.

## `ImportError: cannot import name 'TypeAlias'` on Python 3.9

The codebase uses PEP 604 union syntax (`int | None`) which requires Python 3.10 or newer. Upgrade your Python installation.

---

For anything not covered here, check the docstrings and tests of the relevant module, or open an issue on [GitHub](https://github.com/saiko-psych/semiautomatic_termino).
