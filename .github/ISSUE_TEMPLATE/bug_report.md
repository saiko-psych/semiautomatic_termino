---
name: Bug report
about: Something that worked stopped working, or a behaviour clearly disagrees with the docs
title: "[BUG] "
labels: bug
assignees: ''
---

## What happened

<!-- One sentence: what did you expect, what did the script do instead. -->

## How to reproduce

<!-- Exact command(s) you ran. Paste the relevant config.json (REDACT credentials), the relevant section of the templates if applicable, and the exact stack trace / error message. -->

```
# command(s)


# relevant output / stack trace

```

## Your setup

- **OS:** <!-- e.g. Windows 11, Debian 12 LXC, macOS 14 -->
- **Python:** <!-- output of `python --version` or `uv run python --version` -->
- **uv version:** <!-- output of `uv --version` -->
- **Repo commit:** <!-- output of `git log --oneline -1` -->
- **Mail provider:** <!-- uni-graz-ews / yahoo-smtp / other -->
- **Sheet provider:** <!-- unicloud / google / none -->
- **Calendar provider:** <!-- unicloud-caldav / uni-graz-ews / none -->
- **Run mode:** <!-- manual `uv run python main.py` / systemd timer / Docker / other -->

## What you've tried

<!-- Tests run, alternative configs, things ruled out. -->

## Tests still pass?

- [ ] `uv run python -m unittest discover -s tests` returns OK
