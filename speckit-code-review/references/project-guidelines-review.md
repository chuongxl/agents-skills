# Project Guidelines Advanced Review

Loaded when `docs/guidelines/architecture.md` exists. Uses the project's own architecture doc and the
files it links as the authoritative ruleset for a project-specific review layer on top of the
standard areas.

Everything loaded here is cached and **never re-read**: the architecture context, each guideline file
(in `loaded_guidelines[<stem>]`), the `reference_map`, and the active category set.

## Step 1 — Load or Reuse architecture.md

- **Inside the speckit-auto pipeline**: the Project Context (`arch_pattern`, `repo_map`,
  `linked_guidelines`, `loaded_guidelines`) is already in memory — reuse it, do not re-read.
- **Standalone**: read `docs/guidelines/architecture.md` once and cache it. If it does not exist,
  skip this entire file and run the standard review only.

Log `[Code Review] architecture.md loaded from docs/guidelines/` (or `reused from context`).

## Step 2 — Build the Reference Map

Scan `architecture.md` for a `References` section at any heading level and collect its relative `.md`
links as `{"<file stem>": "docs/guidelines/<filename>.md"}`. For example
`- [Database Rules](database.md)` yields `{"database": "docs/guidelines/database.md"}`.

If there is no `References` section, fall back to scanning the whole file for relative `.md` links.
If the map is still empty, skip Steps 3–6.

## Step 3 — Classify Changed Files

Tag each changed file from the git diff (a file may take several tags); collect the union as
`active_categories`.

| Path pattern | Tag |
|---|---|
| `**/repositories/**`, `**/prisma/**`, `**/migrations/**`, `**/*.schema.*`, `**/*.entity.*` | `database` |
| `**/domain/**`, `**/aggregates/**`, `**/entities/**`, `**/value-objects/**` | `domain` |
| `**/workflow**`, `**/saga**`, `**/state-machine**`, `**/process**` | `workflow` |
| `**/controllers/**`, `**/dto/**`, `**/presentation/**`, `**/routes/**` | `api` |
| `**/auth/**`, `**/security/**`, `**/guards/**`, `**/jwt**` | `security` |
| `**/*.spec.*`, `**/*.test.*`, `**/tests/**` | `testing` |
| `**/config/**`, `**/env/**` | `config` |

## Step 4 — Load Matching Guideline Files

For each tag in `active_categories`, load the `reference_map` entry whose key contains the tag, is
contained by it, or shares its stem. Load only matched files, and only once — check
`loaded_guidelines` first. Never load a guideline with no matching category in the current diff.

## Step 5 — Advanced Review Pass

For each loaded guideline file, check every changed file in its category against its rules, then map
violations onto the standard issue prefixes:

| Violation | Prefix |
|---|---|
| Database / domain / workflow rules | `ARCH-*` |
| Naming conventions | `CODE-*` |
| API or contract rules | `CODE-*` or `FR-*` |

Create a fix entry per violation using the next free ID in that prefix sequence, with `action`
naming the specific project rule broken. Merge these into the standard results **before** writing the
detail files.

## Step 6 — Attribute the Source

Every finding raised by a guideline carries a `guideline_source` in its detail file so the developer
can trace it back:

```json
{
  "id": "ARCH-003",
  "file": "apps/api/src/user/infrastructure/repositories/prisma-user.repository.ts",
  "method": "PrismaUserRepository::findById",
  "lines": "22-35",
  "action": "Return a domain User aggregate, not a raw Prisma record",
  "guideline_source": "docs/guidelines/database.md § Repository Return Types"
}
```
