# Storing secrets

All credentials live in the OS keyring — nothing goes into `config.json`, `sensible.env`, or any other file on disk. The keyring backend is Windows Credential Manager on Windows, macOS Keychain on macOS, and a CryptFile-Keyring on Linux.

## Commands

```bash
# Termino-script secrets: prompts interactively for each credential
# (Termino password, uniCLOUD app-password, Yahoo app-password, etc.)
uv run python -m utils.secrets set --termino

# VPN + EWS credentials: Uni-Graz login password and TOTP base32 seed,
# stored under the openconnect-sso namespace (shared with VPN tooling).
uv run python -m utils.secrets set --email <your-mail@edu.uni-graz.at> --vpn

# Show which keys are present (values are not printed)
uv run python -m utils.secrets list

# Print one value — use carefully
uv run python -m utils.secrets get <key>
```

## EWS credential source

When `mail_provider.type` is `"uni-graz-ews"`, the mail backend authenticates with the user's regular Uni-Graz login password. It reads this from the **openconnect-sso namespace**, not from a separate Termino slot. This is intentional: EWS Basic Auth accepts the same password as the VPN login, which means there is only one password to rotate when the UGO password expires.

Running `set --email ... --vpn` therefore configures both the VPN tunnel and EWS mail in a single step — no separate EWS step is needed.

The `uni-mail-pw` slot in the `termino-uni` namespace is used only by the legacy SMTP-via-mailproxy path. Leave it unset if you use EWS.

## Headless / server setup

On a server without an interactive desktop (LXC, Docker, cron-only VM) the default OS keyring backend requires an interactive unlock prompt that will block cron. Use the plaintext file backend instead:

```bash
export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
```

Set this in the systemd `EnvironmentFile=` so the service picks it up, then restrict permissions:

```bash
chmod 700 ~/.local/share/python_keyring/
chmod 600 ~/.local/share/python_keyring/keyring_pass.cfg
```

`PlaintextKeyring` with `0600` permissions has the same practical security model as an encrypted keyring whose master password is also on disk — both rely on filesystem access control.

## Migrating from a legacy sensible.env

If you have a pre-v2 `sensible.env` file, migrate its values into the keyring once:

```bash
uv run python tools/migrate_env_to_keyring.py
```
