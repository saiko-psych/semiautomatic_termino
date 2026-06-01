---
name: Deployment / VPN / keyring problem
about: Setting up the script on a new server or laptop and something doesn't work
title: "[DEPLOY] "
labels: deployment
assignees: ''
---

> Please read `docs/SERVER_VPN_SETUP.md` and the "VPN setup" + "Storing
> secrets" sections of `README.md` BEFORE opening this. Most "doesn't
> work" cases are a missing step from there.

## What you're trying to do

<!-- "Get this running on a fresh Proxmox LXC", "switch from Yahoo to EWS",
"move from one OS keyring to PlaintextKeyring for cron", etc. -->

## At which step does it fail

<!-- e.g. "openconnect-sso opens the browser, finds the login form, submits, then errors out with X"
     or "main.py crashes at the VPN pre-flight"
     or "uv sync fails to resolve dependencies"
     or "Termino-login is fine, but EWS mail send hangs for 120 s" -->

## Exact command + error

```
# command


# stderr / stdout / journalctl excerpt

```

## Setup details

- **OS:** <!-- e.g. Debian 12 LXC, Ubuntu 24.04, macOS 14 -->
- **Privileged or unprivileged LXC?**
- **Python:** <!-- `python --version` -->
- **uv:** <!-- `uv --version` -->
- **openconnect:** <!-- `openconnect --version` -->
- **openconnect-sso:** <!-- `openconnect-sso --version` -->
- **xvfb-run:** <!-- `which xvfb-run` -->
- **Keyring backend:** <!-- `echo $PYTHON_KEYRING_BACKEND` -->
- **Repo commit:** <!-- `git log --oneline -1` -->

## Reproduction trail

<!-- The exact sequence of steps that led here, copy-pasted from the docs
checklist or a different order if you deviated. -->

## Already-tried hints from the docs

- [ ] `docs/SERVER_VPN_SETUP.md` Troubleshooting section consulted
- [ ] sudoers fragment is in place (`sudo -l` shows the openconnect line)
- [ ] `/dev/net/tun` is present and world-readable
- [ ] Keyring has the expected entries (`python -m utils.secrets list`)
- [ ] Tests pass: `uv run python -m unittest discover -s tests`
