# QA Brainstorm

QA brainstorming is a required core gate between intake and design. It turns gathered evidence into
an approved testing approach before any `test-design.md` or source `.feature` file is authored.

## Inputs

Read the framework-neutral evidence from the active artifact folder and repository:

- `ticket.md`;
- `existing-tests.feature` and `existing-tests-manual.md`, when present;
- repository `.feature` files found during intake;
- declared `--related` and `--impact` hints;
- whether automation was requested, as execution context only.

Do not read framework-specific automation rules here unless they are already injected as project
skills in the session. Automation availability can shape trade-offs, but it must not make core
design framework-specific.

## Conversation

Ask only questions whose answer changes the test design. One question per message. For simple
tickets, still present a short recommended approach and get approval; ceremony scales, approval does
not.

Propose 2-3 approaches when there is meaningful choice. Lead with the recommendation and include
trade-offs, such as:

- UI-heavy coverage;
- API-first with UI smoke;
- thin regression around `NEW` behaviours;
- manual-only or mixed coverage when automation would hide risk.

Borrowed rules from related issues are hypotheses. They become test assertions only when the ticket
states them or a human confirms them here.

## State

Before approval, keep:

```json
"brainstorm": {
  "status": "pending",
  "approach": null,
  "questions": [],
  "confirmed_assumptions": [],
  "rejected_approaches": []
}
```

After approval, set `brainstorm.status: approved`, record the chosen approach, questions and
answers, confirmed assumptions, and rejected approaches. Then set `resume_target: design`.

Design may not start while `brainstorm.status` is `pending`.
