# Stage 05 (github-speckit): YOLO Commit Flow (`--yolo` only)

Load this only when `--yolo` is enabled and `speckit-code-review` is already `pass`.

1. Skip all human review/approval interactions.
2. Auto-generate the commit message:
   `feat(<artifact_id>): <short summary from spec.md or Jira summary>`
   (`artifact_id` — see ../shared/commit.md)
3. Run the commit procedure in [../shared/commit.md](../shared/commit.md) with that message.

## Notes

- The completion step (Stage 06) still runs after this stage.
