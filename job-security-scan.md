# job-security-scan

This guide explains how to install and use the `job-security-scan` skill.

## What This Skill Does

`job-security-scan` runs a full security scan for one or more repositories and combines multiple tools in one workflow:

- Gitleaks (secret scanning in git history)
- Trivy (CVE and config scan)
- Semgrep (SAST)
- Hadolint (Dockerfile lint)
- OSV-Scanner (dependency vulnerabilities)
- TruffleHog (credential verification)

The skill definition is located at:

- `skills/job-security-scan/SKILL.md`

## Install the Skill

Copy the skill folder from this repository into your target skill location.

### Option 1: GitHub Copilot Skill in a Repository

```bash
cp -R skills/job-security-scan /path/to/your-repo/.github/skills/
```

### Option 2: Claude Local Skills Folder

```bash
cp -R skills/job-security-scan ~/.claude/skills/
```

After copying, restart your IDE or agent session.

## Configure the Skill

Update the repository configuration file before scanning:

- `skills/job-security-scan/assets/repository.md`

Set at least:

- `team`
- `org`
- `monorepo-root`
- `package-manager`
- `stack` (update technology stack values to match your services)
- `repos` (update repository names and scan flags)

Important:

- Keep `stack` aligned with your actual tech stack so the correct Semgrep rulesets are applied.
- Keep `repos` aligned with the current repository list so scans run on the right targets.

## Run the Scan

From your target repository:

```bash
# Install required tools
bash .github/skills/job-security-scan/scripts/install-tools.sh

# Run full scan
bash .github/skills/job-security-scan/scripts/run-scan.sh

# Scan one repo only
bash .github/skills/job-security-scan/scripts/run-scan.sh --repo your-repo-name

# Run one scanner only
bash .github/skills/job-security-scan/scripts/run-scan.sh --scanner trivy
```

## Output

Results are saved to the configured output directory (default: `.security-scan-results`) and include:

- JSON scan outputs
- HTML security report

## Troubleshooting

- Verify `repository.md` is valid and all repo names are correct.
- Ensure network access is available for first-time tool installs and DB downloads.
- If a tool is missing, rerun `install-tools.sh`.
