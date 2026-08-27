# Stage 02 — QA Design & Dedup

Stage 02 handles interactive QA brainstorming, output summary review/approval, scenario authoring, deduplication, and QA review.

## Steps

1. **Brainstorming Interview:** Conduct a focused interview (one question at a time) to clarify test scope, constraints, and surface focus (`ui`, `api`, `manual`, `mixed`).
2. **Output Summary & Approval Gate:** Present full Output Summary (Recommended Approach, Q&A Summary, Rejected Approaches, Scope/Risk Boundaries) in chat and **STOP** for explicit human approval.
3. **Draft Design & Scenarios:** Author `test-design.md` and framework-neutral source `.feature` files under `specs/qa/<issue>/`.
4. **Deduplication:** Run `python3 speckit-qa-auto/scripts/dedup-gherkin.py` against existing `.feature` files and label scenarios (`NEW`, `SKIP`, `REVIEW`).
5. **QA Review Gate:** Verify acceptance criteria coverage, framework neutrality, and YAGNI compliance. On approval, update `run.json` to `review.status: passed` and set `resume_target: automation`.
