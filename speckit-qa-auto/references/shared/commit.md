# Shared: Commit & Push Procedure

This reference defines standard git commit and push operations across pipeline stages for `speckit-qa-auto`.

## Commit Rules

1. **Explicit Paths Only.** Never use `git add -A` or `git add .` when unrelated working-tree changes may exist. Add only files explicitly created or modified by the active stage (e.g. `specs/qa/<issue>/` and derived test files).
2. **Commit Check.** Always check `git status --porcelain` before committing. If the working tree is clean, skip the commit step without treating it as an error.
3. **Commit Messages:**
   - Stage 02: `docs(qa): add test design and feature files for <issue>`
   - Stage 03: `test(qa): implement and verify automated tests for <issue>`
   - Stage 04: `docs(qa): update run state to completed for <issue>`

## Sync & Push Procedure

1. `git pull --rebase origin <branch>` (resolve conflicts if any).
2. `git push origin <branch>`.
3. If `--pr` was requested, create or update the Pull Request using `gh pr create` or host capabilities.
