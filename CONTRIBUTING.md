# Contributing

Thanks for considering a contribution. This project is small and informal — pull requests and issue reports are both welcome.

## Quick start

```bash
git clone https://github.com/saiko-psych/semiautomatic_termino.git
cd semiautomatic_termino
uv sync --extra dev
uv run python -m unittest discover -s tests
```

All 90 tests should pass offline (no network, no real credentials needed).

## Layout

See the [Architecture section in the README](README.md#architecture-provider-pattern) for the high-level provider pattern and a per-module breakdown. The important entry points are:

- `main.py` — daily workflow
- `utils/` — provider implementations and helpers
- `tests/` — offline unit tests
- `tools/` — one-off scripts (calendar test, sort tool, migration)

## Workflow

1. Open an issue first for anything bigger than a typo — it's much faster to align on direction before code is written.
2. Branch from `main`, name the branch after the issue.
3. Run tests locally before pushing: `uv run python -m unittest discover -s tests`.
4. Keep the diff small and the commit messages descriptive.
5. Open a PR.

## Code conventions

- **Python 3.10+** syntax. PEP 604 union types (`int | None`), structural pattern matching, etc. are fine.
- **Defensive parsing on user-facing data.** A single bad row in the spreadsheet must not crash the daily cron. Use `pd.to_datetime(..., errors='coerce')`, guard for `NaN`, log a warning, continue.
- **No plaintext secrets, ever.** Credentials come from `utils.secrets.get_secret(name)`. New backends must use the keyring too.
- **Single-file artifacts for tools and templates.** Stay close to "no installation required" so the script is easy to vendor in.
- **Idempotency at the day level.** Anything written to Termino, calendars, or mail must be safe to call twice on the same day.

## Tests

Tests are pure stdlib `unittest`. Run with:

```bash
uv run python -m unittest discover -s tests
# or
uv run pytest
```

No network calls, no real keyring access — mocks all the way down. If you add a new provider, mock the underlying client; do not call out to the real service in a unit test.

## Adding a new provider

The three plug-in points each follow the same shape:

1. Subclass the ABC (`MailSender`, `SheetProvider`, `CalendarSink`).
2. Add a branch to the factory (`make_sender` / `make_sheet_provider` / `make_calendar_sink`).
3. Add a unit test that exercises the new branch with mocked dependencies.
4. Document the new `config.json` shape in `config.example.json`.

That's it.

## Reporting bugs

Use [GitHub Issues](https://github.com/saiko-psych/semiautomatic_termino/issues). Useful info to include:

- Python version (`python --version`)
- OS
- Which provider configuration is active (`config.json` minus secrets)
- The full traceback if there is one
- The last 30 or so lines of stdout from the crashed run

Security issues should go through a private advisory — see [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the same GPL-3.0-or-later as the rest of the project.
