# Project Guidelines Advanced Review

Load this reference file during the review procedure when `docs/guidelines/architecture.md` exists.

## Purpose

Use the project's own `architecture.md` (and the reference files it links to) as the authoritative
ruleset for an advanced, project-specific review layer — on top of the standard review areas.

---

## Step 1 — Load (or Reuse) architecture.md

Check whether the Project Context was already loaded by `speckit-auto` preflight:

- **Inside speckit-auto pipeline**: the Project Context (including `arch_pattern`, `repo_map`,
  `linked_guidelines`, `loaded_guidelines`) is already in memory. Reuse it directly — do NOT
  re-read `architecture.md`.
- **Standalone invocation**: check whether `docs/guidelines/architecture.md` exists.
  - If it does **not** exist → skip this entire file; proceed with standard review only.
  - If it **exists** → read it once and cache it as the architecture context.

Log: `[Code Review] architecture.md loaded from docs/guidelines/` (or `reused from context`).

---

## Step 2 — Discover Reference Links in architecture.md

Scan `architecture.md` for a section named **`References`** (any heading level,
e.g. `## References`, `### References`, `### 3.7 References`).

If such a section exists, collect all relative `.md` links from it into a reference map:

```
reference_map = {
  "<stem>": "docs/guidelines/<filename>.md",
  ...
}
```

Example — if References section contains:
```
- [Database Rules](database.md)
- [Naming Conventions](naming-convention.md)
- [Workflow Rules](workflow-rule.md)
```

Then:
```json
{
  "database": "docs/guidelines/database.md",
  "naming-convention": "docs/guidelines/naming-convention.md",
  "workflow-rule": "docs/guidelines/workflow-rule.md"
}
```

If no `References` section exists, also scan the **entire file** for relative `.md` links and
collect them all into `reference_map` as a fallback. Use the file stem as the key.

If `reference_map` is empty after both passes → skip Steps 3–5; proceed with standard review only.

---

## Step 3 — Classify Changed Files into Categories

Inspect the changed files from the git diff (same scope used by the standard review):

For each changed file, assign one or more category tags based on:

| File path pattern | Category tag |
|---|---|
| `**/repositories/**`, `**/prisma/**`, `**/migrations/**`, `**/*.schema.*`, `**/*.entity.*` | `database` |
| `**/domain/**`, `**/aggregates/**`, `**/entities/**`, `**/value-objects/**` | `domain` |
| `**/workflow**`, `**/saga**`, `**/state-machine**`, `**/process**` | `workflow` |
| `**/controllers/**`, `**/dto/**`, `**/presentation/**`, `**/routes/**` | `api` |
| `**/auth/**`, `**/security/**`, `**/guards/**`, `**/jwt**` | `security` |
| `**/*.spec.*`, `**/*.test.*`, `**/tests/**` | `testing` |
| `**/config/**`, `**/env/**` | `config` |

A single changed file may belong to multiple category tags.

Collect the full set of category tags from all changed files into `active_categories`.

---

## Step 4 — Match Categories to Reference Files

For each tag in `active_categories`, find the best matching key in `reference_map`:

```
FOR each tag in active_categories:
  find reference_map key where:
    key contains tag  OR  tag contains key  OR  key starts with tag stem
  IF match found AND file not yet loaded:
    load the matched reference file
    cache it in loaded_guidelines[key]
```

Load only the files that match at least one active category.
Never load a reference file that has no matching category in the current diff.
Never load the same file twice — check `loaded_guidelines` first.

---

## Step 5 — Execute Advanced Review Pass

For each loaded reference file, run an additional review pass against the changed code:

1. Read the rules and constraints defined in the reference file.
2. Check every changed file that belongs to the matching category against those rules.
3. Record any violations as additional findings under the appropriate review category:
   - Database/domain violations → add to `ARCH-*` findings
   - Naming violations → add to `CODE-*` findings
   - Workflow violations → add to `ARCH-*` findings
   - API/contract violations → add to `CODE-*` or `FR-*` findings

4. For each violation found, create a fix entry with:
   - `id` — next available ID in the matching prefix sequence
   - `file` — the violating file
   - `method` — the class::method or function where the violation occurs
   - `lines` — line range
   - `action` — one-line imperative fix referencing the specific project rule violated

5. Merge these findings into the standard review results before writing detail files.

---

## Step 6 — Include Guidelines Source in Detail Files

When writing per-category detail files (e.g. `architecture.json`, `code-quality.json`),
for each finding that was raised by a project guideline, add a `guideline_source` field:

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

This lets the developer trace the finding back to the exact project rule.

---

## Caching Contract

- `architecture.md` content: cached in Project Context or local variable — never re-read.
- Each loaded reference file: cached in `loaded_guidelines[<stem>]` — never re-read.
- `reference_map`: built once per review run from `architecture.md` — never rebuilt.
- Active categories: computed once from the git diff — never recomputed.
