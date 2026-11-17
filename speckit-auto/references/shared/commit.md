# Shared: Commit + Push Procedure (Provider-Agnostic)

Used by: the Stage 02 → Stage 03 spec/plan commit gate, the Stage 04 human-review commit (default
mode), the Stage 04 YOLO auto-commit, and Stage 06's two commits (verification artifacts, spec
completion). The procedure is identical; only the commit message source differs:

| Call site | Message |
|-----------|---------|
| Stage 02 → 03 gate | auto: `docs(<artifact_id>): add spec, plan, and tasks` |
| Stage 04 default | asked from the user |
| Stage 04 YOLO | auto: `feat(<artifact_id>): <short summary from the spec or Jira summary>` |
| Stage 06 verification artifacts | auto: `chore(verify-<app>): update verification for <artifact_id>` |
| Stage 06 spec completion | auto: `chore(spec): mark <artifact_id> completed` |

`artifact_id` is always defined: the Jira issue key in `--issue` runs, otherwise the artifact
folder's prefix-slug (e.g. `007-user-export`). Never emit a literal `<issue_id>` placeholder.
For a PR fix use the PR number as the message scope; no artifact folder is required.

## Existing PR push (`--pr-fix` only)

The staging and conditional-commit rules still apply, but stage only paths created or changed by
this run; never stage an initial dirty or staged path. If an initial path cannot be separated
safely, stop with `policy_blocked`. At Stage 02, Stage 04 and the Stage 06 verification-artifact
commit, commit locally and **defer the push**. Stage 06 performs the only required push after its
authorization gate. This replaces Branch Sync + Push below; never pull, rebase or force-push.

Immediately before that push, re-query the open PR and verify its head repository and ref still
match intake. Fetch that exact head into a private temporary ref, confirm the fetched SHA matches
the API head, and require it to be an ancestor of local HEAD. If it is not, stop with `git_error`;
do not overwrite remote work. Push `HEAD` to `refs/heads/<pr_head_branch>` at the authenticated
resolved head-repository URL using an ordinary non-force push, then fetch again and verify its
SHA equals local HEAD. A concurrent update or rejected push is a terminal `git_error`, never a
success. Use argument-vector commands and do not print authenticated URLs or credentials.

## Conditional Commit (Critical)

Implementers commit as they go, so the tree is often already clean by the time this runs; an
empty commit attempt exits non-zero and would produce a false failure. Every commit is therefore
conditional:

1. Check `git status --porcelain` in each repo before committing there.
2. **Empty output → skip that repo's commit** and log `already committed during Stage 03 (<n>
   commits on <branch>)`; verify the work with `git log <base-branch>..HEAD --oneline`. This is a
   success path, not a failure.
3. Non-empty → commit as below.

## Staging Safety Check (every call site, both modes)

Never `git add -A` or `git add .`: that publishes whatever happens to be untracked — a stray `.env`
copy, a key file, run evidence — and in `--yolo` nobody looks at the diff first. Before staging in a
repo:

1. List what would be committed: `git status --porcelain --untracked-files=all`.
2. **Stop with the paths quoted** (no commit, no push; `run_failed` `policy_blocked`) when any
   changed or untracked path matches `.env`, `.env.*` (except `.env.example`), `*.pem`, `*.key`,
   `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`, `*credentials*`, `*.kdbx`, or sits under `.speckit/`,
   `.superpowers/`, `.worktrees/` or a Stage 05 evidence folder. Do not "fix" it by deleting or
   ignoring the file yourself; say what it is and let the human decide.
3. Stage **by explicit path** (`git add -- <path> ...`) taken from the listing: the artifact folder
   plus the files the plan and tasks name. A changed path nothing in the spec, plan or tasks accounts
   for is surfaced, not staged (default mode: ask; `--yolo`: stop with the paths quoted).
4. When `gitleaks` is installed, run `gitleaks protect --staged --redact --no-banner`; a finding
   stops the commit with the file and line only, never the value.

## With Submodules

If modified submodules exist: commit inside each dirty submodule first (run the Staging Safety Check
there, `git add -- <paths>` → `git commit -m "<message>"`), then commit the parent pointer update
and any parent changes. Re-check the parent status **after** the submodule commits — a submodule
commit dirties the parent pointer, so the parent may need a commit even when it looked clean moments
earlier.

## Without Submodules

Staging Safety Check → `git add -- <paths>` → `git commit -m "<message>"`.

## Branch Sync + Push (Required)

After the commit decision (including the already-clean success path), sync and push **each
submodule with local commits ahead of its pushed base first**, then the parent repo — same set
identified in "With Submodules" above:

1. For each such submodule, `cd` into it and run steps 2-4 below inside it before doing the same
   for the parent repo.
2. `git pull --rebase origin <branch>` — if the remote branch does not exist yet, continue to push
   (new branch path). On conflicts: resolve, `git add <files>`, `git rebase --continue`, repeat; if
   unresolvable, stop and report.
3. Push: first push `git push -u origin <branch>`; subsequent `git push origin <branch>`.
4. Push failure → stop and report the exact error.

Repos with no submodules just run steps 2-4 once, against the parent repo — this is the original,
unchanged single-repo behavior.

The stage must leave the implementation commit(s) available on the remote feature branch (and, for
every affected submodule, its own remote branch too).

## Reporting and Failure Handling

Report resulting commits (hash + subject) and the pushed branch. If nothing needed committing,
report the Stage 03 commits instead — never report "no commit" as a failure. A failed commit that
was actually needed, a failed push, or an unresolved rebase is a failure for the stage; a skipped
commit on an already-clean tree is not.
For an initialized run, emit `run_failed` with `reason.code: "git_error"` and a composed bounded
summary before this hard stop, using the shared JSON stdin invocation. Return that terminal
status to the calling stage so it does not emit a second failure or any success boundary.
The exact git error stays in the human diagnostic, never in the event payload. Event write
failure stops instrumentation explicitly; do not try to continue or claim completion.

## Scratch Must Already Be Ignored

Staging by explicit path (above) keeps run scratch out of the feature commit as a second line of
defence; the ignore rules below are the first. Stage 01 guarantees
`.superpowers/` in superpowers mode may be git-ignored if needed. The relocated `ticket.md`
inside the artifact folder is **not** scratch and is committed with the artifacts.
`.speckit/` must also be git-ignored in source and worktree for both providers; check that event
history, discovery records, and locks are not staged before committing.