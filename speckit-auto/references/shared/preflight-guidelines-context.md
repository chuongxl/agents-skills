# Preflight: Guidelines Context Loading

Load during Stage 01, after the selected provider's framework availability/source check passes.
Provider-agnostic — used by both `github-speckit` and `superpowers`.

## Goal

Build one in-memory **Project Context** from `docs/guidelines/architecture.md` and reuse it for all stages.  
Do not reread files already loaded.

## Step 1 — Detect Repo Layout

Set:
- `layout = "monorepo"` if `pnpm-workspace.yaml`, `package.json.workspaces`, or `lerna.json` exists.
- else `layout = "single-repo"`.

Workspaces:
- Monorepo: read workspace globs, resolve existing folders.
- Single-repo: `["."]`.

## Step 2 — Optional Guidelines Gate

If `docs/guidelines/` is missing, log skip and stop this guide (pipeline continues).
If folder exists but `docs/guidelines/architecture.md` is missing, log skip and stop this guide.
Otherwise continue.

## Step 3 — Parse `architecture.md` Once

Extract:
- `arch_pattern`
- `dependency_rule` (one sentence)
- `bounded_context_layout` (compact)
- `repo_map`
- `linked_guidelines` = all relative `.md` links found anywhere, stored as:
  - `{ "<stem>": "<resolved repo-relative path>" }`
- `summary` = <=120 words

### `repo_map` extraction order

1. Use explicit **Repository Map** section if present.
2. Else infer from workspace names:
   - `api|server|backend|service` → `backend`
   - `web|app|frontend|ui|client` → `frontend`
   - `bff|gateway|proxy` → `bff`
   - `config|shared|common|utils|lib` → `shared`
   - `database|db|migrations|data` → `database`
   - otherwise `other`
3. If inferred, set `repo_map.inferred = true`.

## Step 4 — Lazy-Load Linked Guidelines

Do not load linked files during parse. Load only when relevant:

- naming/API/class/method/file decisions → stems containing `naming|convention|style`
- schema/migration/query design → stems containing `database|db|data`
- workflow/process/state-machine design → stems containing `workflow|process|state`
- otherwise pick best stem match from task text; if none, load none

Cache content in `loaded_guidelines[stem]`. Never load same file twice.

## Step 5 — Build Project Context Object

```json
{
  "layout": "<monorepo|single-repo>",
  "workspaces": ["<resolved paths>"],
  "repo_map": { "<workspace-path>": "<role>", "inferred": "<true|false>" },
  "arch_pattern": "<from architecture.md>",
  "dependency_rule": "<one sentence>",
  "bounded_context_layout": "<compact summary>",
  "summary": "<<=120 words>",
  "linked_guidelines": { "<stem>": "<repo-relative path>" },
  "loaded_guidelines": {}
}
```

If `architecture.md` is absent after Step 2 skip logic, set:
- `arch_pattern`, `dependency_rule`, `bounded_context_layout`, `summary`, `linked_guidelines` to `null`.

## Step 6 — Mandatory Downstream Usage

### Routing
- `speckit.plan` and `speckit.tasks` must assign tasks by `repo_map`.
- Role mapping: backend/frontend/bff/database/shared.
- Single-repo: all tasks target `.`.
- Never assign tasks without consulting `repo_map`.

### Architecture Compliance
- Generated structure/code must follow `arch_pattern` + `bounded_context_layout`.
- Apply `dependency_rule` in plan/layer design.

### Guideline Cache Rule
- Check `loaded_guidelines` before loading any linked guideline.

### Prompt Injection Rule
- For `speckit.specify`, `speckit.plan`, `speckit.tasks`, `speckit.implement`:
  - prepend `summary`
  - append relevant `repo_map`
  - include loaded guideline content when applicable

## Step 7 — Persistence Log

Emit one line:

`[Preflight] Context loaded: layout=<monorepo|single-repo>, workspaces=<count>, arch=<arch_pattern|none>, linked_guidelines=<comma-separated stems|none>`

Store it as `preflight_summary` in memory and reuse it (no rereads).
