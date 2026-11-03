# Shai-Hulud check section in every report — Plan (approved 2026-11-03)

**Goal:** the final report shows, for every target, that the Shai-Hulud check ran, its verdict and what it
covered, so a CLEAN result can be checked and a failed check is never silent. Base: v2.5 (`fix/self-security-audit`);
the PR into `main` brings v2.5 and this together. Version 2.5 → 2.6.

- [x] **1 Scanner records what it checked** — `checked` block in `shai-hulud-scan.py` JSON: indicator version and
  release count, dependency files, packages (installed), `package.json` files, install hooks, workflows; host:
  projects, global installs, Python packages, npm cache entries, credential stores. Counts and paths only.
- [x] **2 Report section "🪱 Shai-Hulud check"** in MD/HTML/JSON: one row per repo and this machine — verdict
  (AFFECTED / SUSPICIOUS / CLEAN / ERROR / not run), what was checked, indicator version, raw-output link, runbook
  for AFFECTED, credential stores to rotate for the host.
- [x] **3 Schema** — top-level `shai_hulud`; validator rejects a verdict that contradicts the findings.
- [x] **4 Smaller fixes** — Shai-Hulud in the HTML footer's tool list; a failed check shows as ERROR and never marks
  earlier findings fixed.
- [x] **5 Verify** — tests first; real runs on the sample workspace (AFFECTED, CLEAN, host, forced error); PR.
