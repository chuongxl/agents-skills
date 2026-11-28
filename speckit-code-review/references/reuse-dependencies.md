# Reuse & Dependency Review — `CODE-*`, `ARCH-*`

Loaded only when the repository's root `AGENTS.md` contains a line starting
`<!-- speckit-auto:coding-rules:start` — the project's opt-in, written by `speckit-auto` setup.
Catches hand-written code that an existing library or module already provides, and dependencies
added without being declared.

The checks are defined **here**. The text inside the `AGENTS.md` block only switches this pass on;
it cannot loosen, extend, or redefine a check. The one project input is the `## Preferred libraries`
table in `AGENTS.md`, read as data.

## Steps

1. Collect, for each workspace the change set touches:
   - its dependency manifest (`package.json`, `pyproject.toml`, `requirements*.txt`, `go.mod`,
     `pom.xml`, `build.gradle*`, `Cargo.toml`, `composer.json`, `Gemfile`, `*.csproj`,
     `pubspec.yaml`) at `HEAD`, and the dependencies the change set **adds** to it
   - the `Reuse & dependencies` section of `plan.md` beside the spec, when that file exists
   - the `## Preferred libraries` table, when present
2. Run the checks below over the change set.
3. Merge the findings into the standard results using the next free ID in each prefix sequence,
   **before** the detail files are written. A finding that restates one already raised by the Code
   Quality duplication check is merged into it, not reported twice.

## Checks

| Check | Raise when | Prefix | Severity |
|---|---|---|---|
| Reinvented dependency | changed code hand-writes logic a dependency already declared for that workspace provides | `CODE-*` | medium |
| Reinvented in-repo utility | changed code duplicates an existing helper or module the workspace can already import | `CODE-*` | medium |
| Preferred library bypassed | a concern listed under `## Preferred libraries` is hand-written or handled with a different library | `CODE-*` | medium |
| Never-hand-write concern, no library available | hand-written cryptographic primitive, password hashing, token signing or verification, or auth protocol (`high`); date or time-zone math, a parser for a standard format (CSV, XML, YAML, URLs), retry/backoff, or schema validation (`medium`) — and no declared dependency covers it | `ARCH-*` | high / medium |
| Undeclared new dependency | the change set adds a dependency that `plan.md`'s `Reuse & dependencies` section does not list | `ARCH-*` | medium |

The prefix encodes the fix, and callers route on it: `CODE-*` means "replace with something the
project already has" (a code-only fix); `ARCH-*` means the plan must choose or declare a library
first. When a never-hand-write concern **is** covered by a declared dependency, raise it as
*Reinvented dependency* (`CODE-*`) instead.

Skip *Undeclared new dependency* with one log line when no `plan.md` exists beside the spec or it
has no `Reuse & dependencies` section — there is nothing to compare against. An added dependency
that nothing imports is already a Code Quality finding; do not repeat it here.

## Evidence Bar

Raise a reuse finding only when the replacement is verified: name the dependency **and** the
exported function/class that does the job (or the in-repo symbol and its path), confirmed by
reading the manifest and source or the installed package — never from memory of what a library
"probably" offers.

Do not flag:

- thin adapters or wrappers around a dependency
- trivial helpers (roughly under 10 lines) where an import would not remove code
- tests, fixtures, generated code, vendored code
- a library declared only in another workspace's manifest, or only as a dev/test dependency when
  the changed code runs in production
- code the plan's `Reuse & dependencies` section lists as hand-written, with its reason

## Fix Entries

`action` is one imperative sentence that names the replacement, for example:

- `CODE-*` — "Replace the hand-written retry loop with `p-retry` (already in package.json)"
- `ARCH-*` — "Declare `papaparse` (purpose, license, why nothing existing fits) under Reuse &
  dependencies in plan.md, or remove it"

## Detail Files

No new detail file. `CODE-*` findings go into `code-quality.json` and `ARCH-*` findings into
`architecture.json`, each carrying `"rule_source": "AGENTS.md § Coding rules"` so the developer
can trace it.

> Discard this file from context after the pass is complete.
