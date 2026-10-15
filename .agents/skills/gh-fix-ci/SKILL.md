---
name: gh-fix-ci
description: Inspect and repair failing GitHub Actions checks for a UCL branch or pull request.
---

Use GitHub CLI directly; no PR is required for branch CI:

```sh
gh run list --branch <branch> --commit <sha>
gh run view <run-id> --log-failed
```

Fix failures within the user's authorized scope, run relevant local checks,
and push when authorized. Existing authorization covers routine fixes without
another approval cycle. Follow the run for the pushed SHA and report its URL
and conclusion. Inspect external-provider checks through their available tools.
