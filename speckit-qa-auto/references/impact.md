# Impact Analysis

Impact analysis is a core gate between intake and brainstorming. It answers a question no other
part of this skill asks.

## Why This Exists

A story tells you what a feature does. It rarely tells you what the feature *breaks*.

Intake gathers evidence in order to **deduplicate** — to find what is already covered so the design
does not write it twice. None of that answers a different and equally necessary question: *which
existing flows does this story impose a new rule on?*

A story that attaches an invoice to a work order candidate creates an invariant for every flow that
already writes candidates. None of those flows' tickets say so, because they were written before
the invariant existed. Without this sweep the run reports full coverage while the invariant it
created goes untested.

More input is not the fix. A constraint stated in the ticket's own Out-Scope section was already
fetched and already in context when the design was written; what was missing was a question whose
scope the extraction did not set. This file supplies that question.

## Evidence, Never Verdicts

**This is the rule the rest of the file exists to protect.** Every entry this sweep returns is
something that *exists*: a flow name, a file path with a line number, an entity name, a test path.
No entry is a judgement — not `affected: true`, not `risk: high`, not "needs regression".

The reason is mechanical. If the sweep formed coverage or risk judgements, the approved scenario set
would vary between runs over identical inputs, and the guarantee would be gone with nothing
announcing its departure. So: the sweep finds, design decides, a human approves.

An entry claiming a flow *is* affected has exceeded its mandate. Its result is evidence to be
re-read, not a conclusion to adopt.

## Branch A — Entity Mutation Traceability

Finds what may break that nothing currently tests. This branch reaches flows nobody has written a
test for, which is where risk is highest and dedup evidence is blindest.

1. **Resolve the primary entity from `ticket.md`.** The navigation path, the requirements table, and
   the acceptance criteria name it between them. A story headed "Candidate Monitoring" whose
   requirements attach invoice data to candidates resolves to `work_order_candidate`.

2. **Find every write operation against that entity** in the source the repository exposes — the
   frontend, the API schema, the service layer, whichever is reachable. Record the operation and the
   path and line where it is declared.

   Worked example from one real run, showing the shape of the result:

   | Operation | Evidence |
   |---|---|
   | `UpdateWorkOrderCandidateAmendment` | `src/graphql/work-order-candidate.graphql:111` |
   | `RefreshWorkOrderCandidates` | `src/graphql/work-order-candidate.graphql:123` |
   | `ReassignWorkOrderCandidateVendor` | `src/graphql/work-order-candidate.graphql:211` |
   | `CancelWorkOrderCandidates` | `src/graphql/work-order-candidate.graphql:283` |

3. **Map each operation to the flow that calls it and the screen that flow belongs to.**
   `RefreshWorkOrderCandidates` is the Change Setting flow — the one that removes and regenerates
   candidates, and therefore the one an invoice attachment must survive.

That result comes from the ticket plus the source, with no inference about business intent. The
worked example matters for exactly that reason: the flow a human would otherwise have had to
remember is reachable mechanically.

## Branch B — Test Inventory

Finds which existing tests a human should re-run. Consumes the coverage intake already gathered —
`existing-tests.feature`, `existing-tests-manual.md`, any `existing-tests-<KEY>*` exports from
`--related`, and the repository `.feature` paths — and records those exercising the same entity or
the same screen.

Returns file paths and scenario names. **Never a prediction that a test will fail** — whether it
breaks is what running it determines, and a prediction here is the verdict this file forbids.

Its output is a regression **recommendation** carried to finish, not automation scope. Automating
those tests inside this run would put work in scope that has no design, no review, and no verdict
path.

## Why The Two Branches Are Not Redundant

They answer different questions and neither subsumes the other:

- Branch A: *what can break that nobody tests?*
- Branch B: *what tests must be re-run?*

A flow both branches return is a stronger candidate than one only a single branch found, and the
merged record keeps both provenances so that strength stays visible rather than averaged away.

A third approach — searching by domain vocabulary drawn from the ticket — is deliberately not run.
On a mature project it returns most of the system, which is noise priced as signal.

## Ordering

Branch B consumes intake's coverage exports, so this sweep runs **after** intake completes, not
beside it. Branch A needs only `ticket.md` and the repository source.

## Declarations Are Merged With Findings, Never Into Them

A human may declare flows directly with `--impact`. Those declarations and the sweep's findings are
kept in **separate fields**, and each candidate records which produced it: `sweep`, `declared`, or
`both`.

Collapsing them into one list destroys three distinct signals at once — a flow the human knew about
and the sweep confirmed, a flow the sweep found that the human did not think of, and a flow the
human named that the sweep could not reach. The third is the most important, because it is the one
that says the sweep has a blind spot.

## Bounds

This is a read sweep, not a crawl:

- **One hop.** Entity → the operations that write it → the flow that owns each. Not onward to
  entities those flows also touch: two hops from a central entity reaches most of the system.
- **The entity set comes from the ticket, never widened by association.** `work_order_candidate`,
  not also `work_order` because the names look related. A ticket may name more than one entity; it
  never licenses inferring one.
- **Paths and line numbers, never file contents.** The evidence is the pointer, not the code.
- **A result larger than a page returns the entries and a count of what was truncated.** A silent
  cap reads as a complete answer.

## When The Sweep Cannot Run

Absent repository source, an uninitialized submodule, or an entity that cannot be resolved from the
ticket: record that it did not run, and **why**, in `impact.reason`.

Empty-because-nothing-writes-this-entity and empty-because-the-sweep-could-not-run are different
facts, and every consumer downstream treats them differently. Neither releases the design gate, and
neither excuses QA review: a reviewer with no candidate list still runs, with less ammunition for
the invariants question, and the report says so.

## Artifact

Write `docs/qa/<issue>/impact-candidates.md`:

```markdown
# Impact candidates — MOM-1234

Sweep: `ran: true`, `reason: ok`. Entity: `work_order_candidate`.
Declared by the human (`--impact`): none.

| Flow | Evidence | Writes | Existing tests | Source |
|---|---|---|---|---|
| `RefreshWorkOrderCandidates` | `src/graphql/work-order-candidate.graphql:123` | `work_order_candidate` | — | sweep |
| `CancelWorkOrderCandidates` | `src/graphql/work-order-candidate.graphql:283` | `work_order_candidate` | — | sweep |
```

## State

Mirror the artifact into `run.json.impact`, then set `resume_target: brainstorm`:

```json
"impact": {
  "ran": true,
  "reason": "ok",
  "entities": ["work_order_candidate"],
  "declared": [],
  "candidates": [
    {
      "flow": "RefreshWorkOrderCandidates",
      "evidence": "src/graphql/work-order-candidate.graphql:123",
      "writes": "work_order_candidate",
      "existing_tests": [],
      "source": "sweep"
    }
  ],
  "approved_scenarios": [],
  "dropped_scenarios": [],
  "acknowledged_empty": false
}
```

`impact.reason` is one of `ok`, `no-source-access`, `entity-unresolved`, or `not-run`. `not-run` is
the pre-sweep value only; it may not survive past this gate.

`approved_scenarios` and `dropped_scenarios` stay empty here. They are written later: scenarios
exist only after design, so the human approves concrete text rather than a flow name. An empty
`approved_scenarios` is meaningless on its own — it is read together with `acknowledged_empty`, the
record that a person said there is no impact. `ran: false` implies neither.

A candidate is satisfied by a scenario **or** by a recorded drop. Dropped candidates keep their
reason and are never deleted, so a resumed run honours a drop instead of regenerating a scenario a
human already rejected.

## Red Flags — thoughts that mean the sweep has exceeded its mandate

| Thought | Reality |
|---|---|
| "This flow obviously breaks, I'll mark it affected" | The sweep records that the flow writes the entity, with the path and line. Whether it breaks is decided later, by a human reading a designed scenario |
| "The human didn't declare it, so it probably doesn't matter" | Declarations and findings are independent evidence. A finding nobody declared is the case the sweep exists for |
| "The human declared a flow I can't find in the code, I'll drop it" | Record it with `source: declared`. A declaration the sweep cannot reach is the strongest available signal that the sweep has a blind spot |
| "One more hop would find the related entity" | One hop. Two from a central entity returns most of the project as if it were relevant |
| "There are forty candidates, I'll return the ten that look most relevant" | Return them all, or return a page and the count of what was cut. Ranking is a verdict, and picking the interesting ones silently is ranking |
| "No source access, so record zero candidates and move on" | Zero-because-nothing-writes-it and zero-because-the-sweep-could-not-run are different facts. Record which one happened, every time |
| "The story is small, so skip the sweep" | The gate asks its question on every run, and an unrun sweep still has to say it did not run |

---

Provenance: restored from `references/shared/impact-analysis.md`, deleted in commit `4f0ca73`, and
adapted to the flat reference layout and JSON run state. Design rationale:
`docs/superpowers/specs/2026-08-20-speckit-qa-auto-impact-analysis-design.md`.
