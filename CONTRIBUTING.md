# Development and version control

The existing repository is `https://github.com/aryanrawat00/FraudSentinel.git`.
Local development currently uses `main`, tracking `origin/main`. Preserve the
configured remote and current branch unless the repository owner requests a
change. Do not reinitialize Git, force-push, delete branches, or rewrite remote
history.

## Complete and verify one module at a time

1. Inspect `git status --short --branch` and the existing changes before editing.
   Preserve unrelated work and stage only files belonging to the completed module.
2. Implement a small, coherent module and run the relevant local checks. Backend
   changes need applicable Python/API tests; frontend changes need type checking
   and a production build; policy changes need policy/security tests; connected
   workflows need integration or end-to-end verification.
3. Fix failures before committing or pushing. Record the actual commands and
   results; do not claim checks passed if they were skipped or unavailable. For
   documentation or ignore-rule changes, review the diff, run `git diff --check`,
   and verify relevant ignore rules with `git check-ignore`.
4. Review and stage explicit file paths, then inspect the complete staged diff:

   ```powershell
   git diff --check
   git diff --name-status
   git status --short
   # Replace these example paths with the files in the completed module.
   git add -- path/to/changed-file path/to/another-file
   git diff --cached --check
   git diff --cached --stat
   git diff --cached
   ```

5. Create a meaningful commit after successful verification. For example:
   `feat(api): add transaction detail endpoint` or
   `test(security): verify cross-case requests are denied before query execution`.
   Do not include unrelated files or secrets in the commit.

Application setup, test, build, and migration commands are documented in
[README.md](README.md). Run the PostgreSQL integration check when changing the
schema, and browser tests when changing the connected React/API workflow.

## Review before every push

Fetch the current remote state without modifying the working tree, deleting
remote-tracking branches, or changing the current branch:

```powershell
git fetch origin
git status --short --branch
git rev-list --left-right --count origin/main...HEAD
git merge-base --is-ancestor origin/main HEAD
```

For `main`, the first count must be zero and the ancestor check must succeed. If
the remote has changes missing locally, stop the push, inspect those changes, and
integrate them without rewriting published commits. Re-run affected checks after
integration. Never bypass a non-fast-forward rejection with a force push.

Before pushing, show the repository owner all outgoing commits, the changed-file
list, a concise explanation of the changes, and the local verification results:

```powershell
git log --oneline origin/main..HEAD
git diff --name-status origin/main HEAD
git diff --stat origin/main HEAD
git log --format=fuller --stat origin/main..HEAD
git log -p origin/main..HEAD
```

Review every outgoing commit for sensitive content, including files added and
then removed in later commits. Once verification and review are complete, push
normally to the existing branch and verify synchronization:

```powershell
git push origin main
git status --short --branch
git ls-remote --heads origin main
git rev-parse HEAD
```

These commands match the current `main`/`origin/main` setup. If the owner later
changes branches, use that branch's existing upstream instead of switching back
to `main` or changing its remote. Ask the owner to complete authentication or any
required approval when prompted; never request credentials in chat or embed
tokens in commands or remote URLs.

## Secrets and data

- Never commit or push API keys, passwords, database credentials, private keys,
  real customer records, or other sensitive data, including in logs, notebooks,
  screenshots, reports, fixtures, or documentation.
- Keep runtime configuration in ignored environment files. Only `.env.example`
  files containing empty values or obvious placeholders may be committed. Review
  each example before staging it. Frontend environment values are visible to
  browser users and must never contain secrets.
- Use synthetic data for development and demonstrations. Commit generators and
  small, reviewed synthetic test fixtures; keep local/generated datasets,
  database storage, dumps, ML artifacts, and investigation exports ignored.
- Keep source files, migrations, policy examples, dependency manifests, and
  dependency lockfiles tracked. Do not use a blanket `*.sql`, `*.json`, or `*.csv`
  ignore rule that would hide legitimate source or test files.
- `.gitignore` does not protect already tracked files or detect credentials
  embedded in source code. Inspect `git ls-files` and every outgoing commit;
  never use `git add -f` to bypass sensitive-file exclusions.
- If a secret is found, stop the push and notify the owner so it can be revoked
  or rotated. Removing it from the latest file does not remove it from earlier
  commits. Coordinate remediation without force-pushing or overwriting remote
  history.
