# Jira to Speckit Execution Report

## Metadata

- Jira Issue Key: {{JIRA_ISSUE_KEY}}
- Jira Title: {{JIRA_TITLE}}
- Speckit Name: {{SPECKIT_NAME}}
- Repository: {{GITHUB_OWNER}}/{{GITHUB_REPO}}
- Started At: {{START_TIME}}
- Last Updated At: {{LAST_UPDATED_TIME}}
- Current Phase: {{CURRENT_PHASE}}
- Status: {{STATUS}}

## Progress Summary

- Completed Steps: {{COMPLETED_STEPS}}
- Total Steps: {{TOTAL_STEPS}}
- Progress Percent: {{PROGRESS_PERCENT}}
- Current Blocker: {{CURRENT_BLOCKER}}

## Step Execution Log

| Step | Phase | Status | Progress | Issue | Copilot Requests | Input Tokens | Response Tokens | Cost Estimate |
|------|-------|--------|----------|-------|------------------|--------------|-----------------|---------------|
| 1 | Jira Intake | {{STEP1_STATUS}} | {{STEP1_PROGRESS}} | {{STEP1_ISSUE}} | {{STEP1_REQUESTS}} | {{STEP1_INPUT_TOKENS}} | {{STEP1_RESPONSE_TOKENS}} | {{STEP1_COST}} |
| 2 | Specify | {{STEP2_STATUS}} | {{STEP2_PROGRESS}} | {{STEP2_ISSUE}} | {{STEP2_REQUESTS}} | {{STEP2_INPUT_TOKENS}} | {{STEP2_RESPONSE_TOKENS}} | {{STEP2_COST}} |
| 3 | Spec Clarification Loop | {{STEP3_STATUS}} | {{STEP3_PROGRESS}} | {{STEP3_ISSUE}} | {{STEP3_REQUESTS}} | {{STEP3_INPUT_TOKENS}} | {{STEP3_RESPONSE_TOKENS}} | {{STEP3_COST}} |
| 4 | Plan | {{STEP4_STATUS}} | {{STEP4_PROGRESS}} | {{STEP4_ISSUE}} | {{STEP4_REQUESTS}} | {{STEP4_INPUT_TOKENS}} | {{STEP4_RESPONSE_TOKENS}} | {{STEP4_COST}} |
| 5 | Plan Clarification Loop | {{STEP5_STATUS}} | {{STEP5_PROGRESS}} | {{STEP5_ISSUE}} | {{STEP5_REQUESTS}} | {{STEP5_INPUT_TOKENS}} | {{STEP5_RESPONSE_TOKENS}} | {{STEP5_COST}} |
| 6 | Tasks | {{STEP6_STATUS}} | {{STEP6_PROGRESS}} | {{STEP6_ISSUE}} | {{STEP6_REQUESTS}} | {{STEP6_INPUT_TOKENS}} | {{STEP6_RESPONSE_TOKENS}} | {{STEP6_COST}} |
| 7 | Tasks Clarification Loop | {{STEP7_STATUS}} | {{STEP7_PROGRESS}} | {{STEP7_ISSUE}} | {{STEP7_REQUESTS}} | {{STEP7_INPUT_TOKENS}} | {{STEP7_RESPONSE_TOKENS}} | {{STEP7_COST}} |
| 8 | Implement | {{STEP8_STATUS}} | {{STEP8_PROGRESS}} | {{STEP8_ISSUE}} | {{STEP8_REQUESTS}} | {{STEP8_INPUT_TOKENS}} | {{STEP8_RESPONSE_TOKENS}} | {{STEP8_COST}} |
| 9 | GitHub Branch and PR | {{STEP9_STATUS}} | {{STEP9_PROGRESS}} | {{STEP9_ISSUE}} | {{STEP9_REQUESTS}} | {{STEP9_INPUT_TOKENS}} | {{STEP9_RESPONSE_TOKENS}} | {{STEP9_COST}} |

## Cumulative AI Usage

| Metric | Value |
|--------|-------|
| Total Copilot Requests | {{TOTAL_REQUESTS}} |
| Total Input Tokens | {{TOTAL_INPUT_TOKENS}} |
| Total Response Tokens | {{TOTAL_RESPONSE_TOKENS}} |
| Estimated Total Cost | {{TOTAL_ESTIMATED_COST}} |

## Cost Estimation Basis

| Parameter | Value |
|-----------|-------|
| Input Token Rate | {{INPUT_TOKEN_RATE}} |
| Response Token Rate | {{RESPONSE_TOKEN_RATE}} |
| Cost Formula | (Input Tokens x Input Rate) + (Response Tokens x Response Rate) |
| Estimation Mode | {{ESTIMATION_MODE}} |

## Issues and Decisions

| Time | Phase | Type | Description | Action Taken | Owner |
|------|-------|------|-------------|--------------|-------|
| {{ISSUE_TIME_1}} | {{ISSUE_PHASE_1}} | {{ISSUE_TYPE_1}} | {{ISSUE_DESC_1}} | {{ISSUE_ACTION_1}} | {{ISSUE_OWNER_1}} |
| {{ISSUE_TIME_2}} | {{ISSUE_PHASE_2}} | {{ISSUE_TYPE_2}} | {{ISSUE_DESC_2}} | {{ISSUE_ACTION_2}} | {{ISSUE_OWNER_2}} |

## Final Outcome

- Ended At: {{END_TIME}}
- Final Status: {{FINAL_STATUS}}
- Final Next Action: {{FINAL_NEXT_ACTION}}
- Artifacts:
  - Spec: {{SPEC_PATH}}
  - Plan: {{PLAN_PATH}}
  - Tasks: {{TASKS_PATH}}
  - Branch: {{BRANCH_NAME}}
  - PR: {{PR_URL}}
