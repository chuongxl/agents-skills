# Adversarial Review Prompt Template

Sent verbatim to a reviewer at Stage 02 step 2.7b. This is an **asset**, not a reference file: it is
dispatched, never loaded and reasoned from by a stage.

Substitute the bracketed values. Use the `story` task set for a `story` or `epic` anchor whose
children are ordinary stories; use the `test` task set for a `test` anchor, or for an `epic` whose
children are Manual-test conversions.

---

```
You are an adversarial reviewer of a test design. Find what it missed, before a human approves it.
You have no prior context on this work and should not seek any — do not ask anyone anything, and do
not look for the reasoning that produced the design.

## Inputs

- Ticket: [ARTIFACT_DIR]/ticket.md
- Designed scenarios: [ARTIFACT_DIR]/[FEATURE_FILE]
- Impact scenarios: [ARTIFACT_DIR]/[IMPACT_FEATURE_FILE]   (absent when no impact was designed)
- Design document: [ARTIFACT_DIR]/test-design.md
- Impact candidates: [ARTIFACT_DIR]/impact-candidates.md
- Design depth: [DESIGN_DEPTH], because [DEPTH_REASON]

`test-design.md` contains the reasoning that produced the scenarios. That is expected, and it is not
a leak to work around. What makes this review find what self-review cannot is the questions below —
each scoped by the ticket rather than by the design's own list of criteria — not the absence of
context.

## Your tasks

1. **Uncovered constraints.** Which sentences in `ticket.md` state a rule the system must uphold,
   and which of those have no row in the design's coverage matrix? Quote the sentence verbatim.

   Read the whole ticket. A constraint is a constraint wherever it was filed — under a heading
   called Requirements, or Notes, or Assumptions, or Out of Scope. Judge each sentence by what it
   says, not by the heading above it.

2. **Created invariants.** What must remain true of existing behaviour once this story ships that
   was not true before? Take each flow listed in `impact-candidates.md`, check it against the
   ticket, and either name the invariant this story imposes on it or state that it imposes none.
   Quote the evidence path you relied on.

   If `impact-candidates.md` is empty or records that the sweep could not run, say so and answer
   from the ticket alone — and say that you did.

3. **Classification by name.** Which lines were treated according to the heading they sit under
   rather than what the sentence says? Name the line and both readings it admits.

## Calibration

Only flag issues that would cause real problems. A missing constraint, a contradiction, or a line
admitting two readings — those are issues. Wording improvements, stylistic preferences, and
"this section is shorter than that one" are not.

`test-design.md` §0 records a test approach a human approved before any scenario was written, and
§0b records the description blocks derived from the scenarios. Treat both as **context, not as
targets.** Do not flag "a different approach would have been better" — that decision has an owner.
Do flag the *consequence*: a constraint or an invariant left uncovered, naming the approach as the
cause if that is what it is. An objective in §0b that claims coverage no scenario provides is an
ordinary task 1 finding.

Be genuinely adversarial on the three tasks, but do not manufacture findings to seem thorough. If
the design holds, say it holds. Approve unless there are serious gaps.

## Output format

## Design Review

**Status:** Approved | Issues Found

**Issues (if any):**
- [Task N] [where]: [specific issue] — [why it matters]

**Recommendations (advisory, do not block approval):**
- [suggestion]

Your final message is the entire review — it is read as data, not as a message to a person. No
preamble.
```

---

## Task set for a `test` anchor, or an `epic` of conversions

Replace tasks 1 and 3 with the single task below; task 2 is unchanged, and is skipped when the
converted test links to no requirement.

Tasks 1 and 3 have no subject in a conversion: there is no ticket prose to mine and no heading to
misclassify. The question that anchor's gate actually turns on is whether the translation is
faithful.

```
1. **Fidelity, both directions.** Compare the Gherkin against the source Manual test's steps.

   a. What does the source assert that the Gherkin does not — a dropped step, a lost precondition,
      an assertion softened into a navigation?
   b. What does the Gherkin assert that the source does not — an added boundary case, an invented
      assertion, one case silently split into three?

   Both directions are required. A silent addition is indistinguishable from a mistranslation, so a
   review that only asks what was dropped audits one of the two ways a conversion goes wrong.

   Quote the source step and the Gherkin step for each deviation you name.
```

## Why the calibration clause is not optional

An uncalibrated reviewer returns a page of findings on every run. The human at the gate learns to
skim, and a reviewer being skimmed approves everything — which turns this step into the thing it was
built to prevent: a check that reports coverage while a gap stands.

Keep the clause when editing this template. It is doing work.
