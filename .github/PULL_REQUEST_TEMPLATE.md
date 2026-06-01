<!-- Thanks for the PR. Keep it small and focused - reviewers will thank you. -->

## What this PR does

<!-- One paragraph. What changed and why. Link an issue with "Closes #N" if applicable. -->

## How to verify

<!-- Specific commands the reviewer can run. -->

```bash
uv run python -m unittest discover -s tests
# expected: Ran NN tests in <1s, OK
```

## Checklist

- [ ] All existing tests still pass (`uv run python -m unittest discover -s tests`)
- [ ] New behaviour has a test
- [ ] No plaintext secrets in any file (including .example files)
- [ ] `config.example.json` updated if a new config field was added
- [ ] README / docs updated if user-facing behaviour changed
- [ ] Commit messages are descriptive (subject + body, imperative mood)
- [ ] No unrelated changes bundled in (CRLF/LF churn, IDE clutter, etc.)

## Notes for reviewer

<!-- Anything non-obvious about the diff. Edge cases you considered. -->
