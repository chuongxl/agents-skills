# Preflight: Guidelines Context Loading

Load this at the start of Stage 01, after the Speckit source check passes.

## Purpose

Read `docs/guidelines/architecture.md` once per pipeline run, build a compact **Project Context**
object, and keep it in memory for all subsequent stages.
Never re-read the same file twice — reference the in-memory context instead.

---

## Step 1 — Detect Repository Layout (Mono vs Single)

Check whether the repo is a monorepo or a single-repo:

```
IF pnpm-workspace.yaml OR package.json workspaces field OR lerna.json EXISTS:
  layout = "monorepo"
ELSE:
  layout = "single-repo"
```

For a **monorepo**, enumerate workspace members:

- Read `pnpm-workspace.yaml` (or the `workspaces` field in `package.json`).
- List all workspace glob patterns (e.g., `apps/*`, `packages/*`).
- Resolve each pattern to folders that exist on disk; record each folder path.

Store the result as:

```json
{
  "layout": "monorepo",
  "workspaces": ["apps/api", "apps/web", "packages/config", "packages/database"]
}
```

or for a single-repo:

```json
{
  "layout": "single-repo",
  "workspaces": ["."]
}
```

---

## Step 2 — Check for docs/guidelines/ and architecture.md

This step is **optional**. If the folder or file is absent, skip the rest of this guide entirely
and continue the pipeline as normal — no error, no stop.

```
IF docs/guidelines/ does NOT exist:
  log: "[Preflight] docs/guidelines/ not found — guidelines step skipped."
  SKIP Steps 3–7, continue pipeline normally

IF docs/guidelines/ exists BUT docs/guidelines/architecture.md does NOT exist:
  log: "[Preflight] docs/guidelines/architecture.md not found — guidelines step skipped."
  SKIP Steps 3–7, continue pipeline normally

OTHERWISE:
  proceed to Step 3
```

---

## Step 3 — Load and Parse architecture.md

Read `docs/guidelines/architecture.md` **once** and extract the following into memory:

| Field | What to capture |
|-------|----------------|
| `arch_pattern` | Core pattern name(s) stated in the file — e.g., `"Clean Architecture + DDD"` |
| `dependency_rule` | The inviolable dependency direction rule, in one sentence |
| `bounded_context_layout` | Folder structure per bounded context, as a compact text summary |
| `repo_map` | Which workspace / app / package serves which role. See inference rules below. |
| `linked_guidelines` | **All relative `.md` file links found anywhere in the file.** Collect them as a map of `{ "<stem>": "<resolved path relative to repo root>" }`. Do not assume any fixed names — capture whatever links exist. |
| `summary` | ≤120-word plain-text summary of the overall architecture, suitable for prompt injection |

### Repository Map — Extraction Order

1. If `architecture.md` has an explicit **Repository Map** section, parse it verbatim.
2. Otherwise, infer roles from workspace folder names using these patterns:

| Name pattern | Inferred role |
|---|---|
| `api`, `server`, `backend`, `service` | `backend` |
| `web`, `app`, `frontend`, `ui`, `client` | `frontend` |
| `bff`, `gateway`, `proxy` | `bff` |
| `config`, `shared`, `common`, `utils`, `lib` | `shared` |
| `database`, `db`, `migrations`, `data` | `database` |
| anything else | `other` |

When inferred, set `"inferred": true` in the repo_map object.

---

## Step 4 — Lazy-Load Linked Guidelines (On Demand)

Do **not** read any linked files immediately after parsing `architecture.md`.
Store only their resolved paths in `linked_guidelines`.

Load a linked file **only when** the current stage's task makes it relevant:

- Before naming any file, class, method, or API endpoint in `speckit.plan` or `speckit.implement` →
  load any guideline whose stem contains `naming`, `convention`, or `style`
- Before designing any database schema, migration, or query in `speckit.plan` →
  load any guideline whose stem contains `database`, `db`, or `data`
- Before designing any state machine, saga, process, or workflow in `speckit.plan` →
  load any guideline whose stem contains `workflow`, `process`, or `state`
- For any other task — scan the task description and load the guideline whose stem best matches
  the topic; if no match, do not load anything

After loading a linked file, cache its full content in memory under its stem key in `loaded_guidelines`.
Never load the same file twice; always check `loaded_guidelines` first.

---

## Step 5 — Build In-Memory Project Context Object

Assemble the full Project Context and hold it for all subsequent stages:

```json
{
  "layout": "<monorepo|single-repo>",
  "workspaces": ["<resolved workspace paths>"],
  "repo_map": {
    "<workspace-path>": "<role>",
    "inferred": "<true|false>"
  },
  "arch_pattern": "<pattern name from architecture.md>",
  "dependency_rule": "<one-sentence inviolable rule>",
  "bounded_context_layout": "<compact folder structure summary>",
  "summary": "<≤120-word architecture summary>",
  "linked_guidelines": {
    "<stem>": "<resolved path relative to repo root>"
  },
  "loaded_guidelines": {}
}
```

`loaded_guidelines` accumulates files as they are loaded on demand:

```json
"loaded_guidelines": {
  "<stem>": "<full file content>"
}
```

If `architecture.md` was not found, set `arch_pattern`, `dependency_rule`,
`bounded_context_layout`, `summary`, and `linked_guidelines` all to `null`.

---

## Step 6 — Mandatory Usage Rules for All Subsequent Stages

### Implementation Routing (Monorepo)

- When `speckit.plan` and `speckit.tasks` create tasks, assign each task to the correct
  workspace using `repo_map`.
- Backend tasks → target the workspace with role `backend`.
- Frontend tasks → target the workspace with role `frontend`.
- BFF tasks → target `bff`. Database tasks → target `database`. Shared → target `shared`.
- For a single-repo (`layout = "single-repo"`), all tasks target `.`.
- Never assign tasks without first consulting `repo_map`.

### Architecture Compliance

- All generated code, folder paths, and module structures must follow `arch_pattern`
  and `bounded_context_layout` from the Project Context.
- Apply `dependency_rule` when designing any layer, service, or module in `speckit.plan`.

### Guideline Loading — Always Check `loaded_guidelines` First

- Before loading any linked guideline, check `loaded_guidelines[stem]`.
  If already present, use the cached content. Never re-read the file.

### Context Injection

- When prompting `speckit.specify`, `speckit.plan`, `speckit.tasks`, or `speckit.implement`,
  always prepend the `summary` from the Project Context.
- Append the relevant `repo_map` entries so the stage knows which workspace to target.
- If a linked guideline has been loaded for the current task, include its content in the prompt.

---

## Step 7 — Context Persistence Summary

After completing preflight, print exactly one log line:

```
[Preflight] Context loaded: layout=<monorepo|single-repo>, workspaces=<count>,
arch=<arch_pattern|none>, linked_guidelines=<comma-separated stems|none>
```

Store this as `preflight_summary` in memory. Reference it in subsequent stages instead of
re-reading any file.
