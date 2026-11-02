# Remediation Guide

Quick reference for fixing each category of findings produced by `job-security-scan`.

---

## 🔑 Secrets in Git History

### Remove from tracking & gitignore
```bash
git rm --cached .env
echo ".env" >> .gitignore
echo ".env*.local" >> .gitignore
git commit -m "chore: remove .env from tracking"
```

### Purge from full git history
```bash
brew install git-filter-repo   # or: pip install git-filter-repo
git filter-repo --path .env --invert-paths --force
git push --force-with-lease origin main
```

### Rotate leaked credentials immediately
- **GitHub PAT**: github.com/settings/tokens → Delete token → Create new
- **Figma key**: Figma → Account Settings → Personal Access Tokens → Revoke
- **AlloyDB password**: Reset via Google Cloud Console → Cloud SQL → Edit instance

---

## 📦 CVE Vulnerabilities

### Update a specific package
```bash
cd <repo>
yarn upgrade <package>@<fix-version>
# Example:
yarn upgrade protobufjs@7.5.5
yarn upgrade typeorm@0.3.26
yarn upgrade next@14.2.25
```

### Batch update all CRITICAL/HIGH (with review)
```bash
yarn upgrade-interactive --latest
```

### Add to .trivyignore if no fix exists
```
# .github/skills/job-security-scan/assets/.trivyignore
CVE-XXXX-XXXXX exp:2025-12-31  # no fix available, risk accepted
```

---

## 🐳 Dockerfile Misconfigurations

### DS-0002: Add non-root USER
```dockerfile
# Add before the final CMD/ENTRYPOINT
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser
```

### Pin base image versions
```dockerfile
# Bad:
FROM node:22-alpine

# Good:
FROM node:22.14.0-alpine3.21
```

---

## 🔍 SAST Findings (Semgrep)

### TypeORM raw query injection
```typescript
// Bad:
await repo.query(`SELECT * FROM users WHERE id = ${userId}`)

// Good:
await repo.query('SELECT * FROM users WHERE id = $1', [userId])
// Or better — use the TypeORM QueryBuilder:
await repo.createQueryBuilder('user').where('user.id = :id', { id: userId }).getOne()
```

### Unsafe JWT verification
```typescript
// Bad:
jwt.verify(token, secret, { algorithms: undefined })

// Good:
jwt.verify(token, secret, { algorithms: ['HS256'] })
```

---

## 🐋 Supply Chain

If Socket Security or Semgrep flags a package:
1. Check the package page on [socket.dev](https://socket.dev)
2. Review the `postinstall` script in `node_modules/<pkg>/package.json`
3. If malicious: remove immediately, audit what the script executed, rotate any credentials accessible to the process

---

## 🪱 Shai-Hulud: if affected

Applies when the `shai-hulud` check says **AFFECTED** for a repo or for this machine. Assume every
credential the machine or CI runner could reach has been stolen. Work in this order:

1. **Stop the spread.** Do not run `npm install` / `npm ci` / `pip install` on the affected machine or
   runner. Disconnect self-hosted runners; disable workflows in affected repos.
2. **Rotate credentials, most dangerous first.** npm tokens (`npm token list`, revoke all, re-create with
   least privilege) → GitHub tokens, SSH keys and OAuth apps → cloud keys (AWS, Azure, GCP) → SSH keys
   elsewhere → everything in `.env` files. Host mode lists the stores present on this machine.
3. **Check your GitHub account and orgs** for what the worm creates:
   repositories you did not create (random names, or descriptions such as `Shai-Hulud`,
   `Shai-Hulud Migration`, `Sha1-Hulud: The Second Coming`), private repos turned public,
   branches named `shai-hulud`, new workflows (`shai-hulud*.yml`, `discussion.yaml`, `formatter_*.yml`),
   and self-hosted runners you did not register (e.g. `SHA1HULUD`). Review the audit log for token use.
4. **Clean the machine.** Delete `node_modules` and lockfile-pinned worm releases, run
   `npm cache clean --force`, remove planted files (`.claude/setup.mjs`, `.vscode/setup.mjs`, worm entries in
   `.claude/settings.json` / `.vscode/tasks.json`), and check global installs. Reinstall from a clean lockfile
   with `npm ci --ignore-scripts` first, then re-enable scripts once the check is clean.
5. **If you publish packages:** check every version you published since the exposure for a `preinstall` /
   `postinstall` you did not write; deprecate and unpublish affected versions, enable trusted publishing
   and 2FA.
6. **Re-run** `run-scan.sh --scanner shai-hulud --host` until the verdict is clean.

For **SUSPICIOUS** findings: install with `--ignore-scripts`, read the flagged script, and report the
package to the registry if it is malicious. Indicator sources: [ioc-data.md](ioc-data.md).

---

## 📋 Priority Order

| Priority | Fix When | Action |
|----------|----------|--------|
| P0 — Shai-Hulud AFFECTED | Immediately | Follow "Shai-Hulud: if affected" above |
| P0 — Verified secrets | Immediately | Rotate + purge from history |
| P1 — CRITICAL CVE | Before next release | `yarn upgrade` |
| P2 — HIGH CVE | This sprint | `yarn upgrade` |
| P3 — Dockerfile misconfig | Next sprint | Add `USER` instruction |
| P4 — SAST findings | Next sprint | Fix per pattern above |
| P5 — MEDIUM CVE | Backlog | Upgrade during dependency maintenance |
