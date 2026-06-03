# semiautomatic_termino

[![tests](https://github.com/saiko-psych/semiautomatic_termino/actions/workflows/tests.yml/badge.svg)](https://github.com/saiko-psych/semiautomatic_termino/actions/workflows/tests.yml)
[![docs](https://readthedocs.org/projects/semiautomatic-termino/badge/?version=latest)](https://semiautomatic-termino.readthedocs.io/en/latest/)

Daily-cron automation around [termino.gv.at](https://www.termino.gv.at/), built for university research groups that manage many participants and supervisors. In one idempotent daily run it logs into Termino, syncs the schedule from your group's cloud spreadsheet, sends confirmation and reminder mails, alerts each supervisor about tomorrow's slot, and (optionally) drops every slot into a shared calendar.

## 📖 Documentation

**The full documentation lives at [semiautomatic-termino.readthedocs.io](https://semiautomatic-termino.readthedocs.io/en/latest/)** — installation, configuration, storing secrets, VPN setup, the daily run, server/cron deployment, the provider architecture, troubleshooting, and the autodoc API reference.

## Quick start

```bash
# 1. Install uv   (Windows PowerShell: irm https://astral.sh/uv/install.ps1 | iex)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and sync
git clone https://github.com/saiko-psych/semiautomatic_termino.git
cd semiautomatic_termino
uv sync

# 3. Configure providers + keyring secrets
uv run python setup.py
```

Then try a single run with `uv run python main.py`. Full details in the
[installation guide](https://semiautomatic-termino.readthedocs.io/en/latest/getting-started/installation.html).

## Status

Active development by the maintainer for the Uni-Graz music-psychology study workflow. This is a personal tool shared publicly because parts of it may be useful to other research groups. **Use at your own risk** — no warranty, no support contract, no affiliation with Uni-Graz IT. Issues and pull requests welcome.

The cross-platform auto-VPN modules (`utils/auto_vpn*.py`, `utils/vpn_provider.py`) are being extracted into a separate repository, [`automatic-openconnect`](https://github.com/saiko-psych/automatic-openconnect); `semiautomatic_termino` will later depend on it as an optional package. No breaking changes are planned for direct users.

## Contributing & license

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the dev workflow. Run the offline test suite with:

```bash
uv run python -m unittest discover -s tests
```

Licensed under [GPL-3.0-or-later](LICENSE).
