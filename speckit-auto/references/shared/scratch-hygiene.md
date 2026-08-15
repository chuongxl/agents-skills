# Shared: Scratch Path Hygiene (Provider-Agnostic)

Load during Stage 01, before any implementation. Required in **both** providers.

Stage 04/05 commit with `git add -A`, so any scratch directory left untracked ends up inside the
feature commit.

| Path | Written by | Applies to |
|---|---|---|
| `.speckit/` | `speckit-code-review` (review detail files, `state.json`), Stage 01 intake staging | both providers |
| `.superpowers/` | `subagent-driven-development` (plan ledger, briefs, review packages) | superpowers only |

Before Stage 03, ensure the applicable entries are ignored in the repo whose tree will be committed:

1. Read `.gitignore` at the repo root.
2. Append any applicable entry that is missing, each on its own line under a short comment.
3. If `.gitignore` does not exist, create it with just those entries.
4. This edit is part of the feature commit — do not commit it separately.

`.superpowers/` may already be excluded by the implementation skill through `.git/info/exclude`;
adding it to `.gitignore` anyway is harmless and survives a fresh clone.

The relocated `<artifact_folder>/ticket.md` is **not** scratch — never add it to `.gitignore`.
