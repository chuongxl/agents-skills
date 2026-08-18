# Jira to Speckit Execution Report

## Metadata

- Jira Issue Key: {{JIRA_ISSUE_KEY}}
- Jira Title: {{JIRA_TITLE}}
- Feature Name: {{FEATURE_NAME}}
- Repository: {{GITHUB_OWNER}}/{{GITHUB_REPO}}
- Started At: {{START_TIME}}
- Last Updated At: {{LAST_UPDATED_TIME}}
- Current Stage: {{CURRENT_STAGE}}
- Status: {{STATUS}}

## Stage Log

| Stage | Status | Progress | Blocker / Issue |
|-------|--------|----------|-----------------|
| Stage 01 — Jira Intake | {{S1_STATUS}} | {{S1_PROGRESS}} | {{S1_ISSUE}} |
| Stage 02 — Spec / Design | {{S2_STATUS}} | {{S2_PROGRESS}} | {{S2_ISSUE}} |
| Stage 03 — Implement + Review Loop | {{S3_STATUS}} | {{S3_PROGRESS}} | {{S3_ISSUE}} |
| Stage 04 — Commit / Completion | {{S4_STATUS}} | {{S4_PROGRESS}} | {{S4_ISSUE}} |

Update this table in place after every stage of the run; optionally append granular per-step rows
(e.g. per Stage 02 stage step) as the run progresses.

## Issues and Decisions

| Time | Stage | Type | Description | Action Taken | Owner |
|------|-------|------|-------------|--------------|-------|
| {{ISSUE_TIME_1}} | {{ISSUE_STAGE_1}} | {{ISSUE_TYPE_1}} | {{ISSUE_DESC_1}} | {{ISSUE_ACTION_1}} | {{ISSUE_OWNER_1}} |
| {{ISSUE_TIME_2}} | {{ISSUE_STAGE_2}} | {{ISSUE_TYPE_2}} | {{ISSUE_DESC_2}} | {{ISSUE_ACTION_2}} | {{ISSUE_OWNER_2}} |

## Final Outcome

- Ended At: {{END_TIME}}
- Final Status: {{FINAL_STATUS}}
- Artifacts:
  - Spec: {{SPEC_PATH}}
  - Plan: {{PLAN_PATH}}
  - Branch: {{BRANCH_NAME}}
  - Implementation commit: {{IMPLEMENTATION_COMMIT}}
  - Spec completion commit: {{COMPLETION_COMMIT}}