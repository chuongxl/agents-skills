# Provenance of the deep-audit method

The files below are copied from [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill)
at commit `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` (2026-09-14), under the MIT License, Copyright (c)
2025-2026 Cloudflare, Inc. The full license text is in [LICENSE-cloudflare.txt](LICENSE-cloudflare.txt).

| File here | Upstream file | Changes |
|---|---|---|
| `METHOD.md` | `skills/security-audit/SKILL.md` | YAML frontmatter removed (so no tool loads it as a separate skill); body unchanged |
| `RECONNAISSANCE.md`, `HUNTING.md`, `VALIDATION-AND-REPORTING.md`, `ATTACK-CLASSES.md` | same names | none |
| `AI-AND-LLM.md`, `CLIENT-SIDE.md`, `CLOUD-AND-DEPLOYMENT.md`, `DATA-ISOLATION-AND-LIFECYCLE.md`, `DESKTOP-MOBILE-AND-LOCAL-IPC.md`, `MEMORY-SAFETY-AND-BINARY.md`, `PROTOCOLS-RPC-AND-MESSAGING.md`, `RESOURCE-EXHAUSTION-AND-AVAILABILITY.md`, `SUPPLY-CHAIN-AND-RELEASE.md`, `WEB-PROTOCOL-AND-AUTH.md` | same names | none |
| `../../assets/audit/findings.schema.json` | `skills/security-audit/report-schema.json` | none |

Not copied: `validate-findings.cjs`, `validate-coverage-ledger.cjs` and their tests. Their rules are ported
to stdlib Python in `scripts/lib/audit.py` (with `scripts/validate-audit.py` as the command line), so the
skill keeps needing only Python. The upstream files mention the Node commands; [WORKFLOW.md](WORKFLOW.md)
maps every upstream command and path to this skill's equivalent.

To update from upstream: copy the same files again, re-apply the one change listed above, run
`python3 -I scripts/test-audit.py` (it checks that the schema still uses only keywords the Python validator
understands), and review the diff of the method files for new rules the port must enforce.
