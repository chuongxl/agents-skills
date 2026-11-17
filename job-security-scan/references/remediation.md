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

## 📋 Priority Order

| Priority | Fix When | Action |
|----------|----------|--------|
| P0 — Verified secrets | Immediately | Rotate + purge from history |
| P1 — CRITICAL CVE | Before next release | `yarn upgrade` |
| P2 — HIGH CVE | This sprint | `yarn upgrade` |
| P3 — Dockerfile misconfig | Next sprint | Add `USER` instruction |
| P4 — SAST findings | Next sprint | Fix per pattern above |
| P5 — MEDIUM CVE | Backlog | Upgrade during dependency maintenance |
