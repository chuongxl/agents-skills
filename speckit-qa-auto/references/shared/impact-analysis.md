# Shared: Impact Analysis

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## Overview

A story tells you what a feature does. It rarely tells you what the feature breaks.

The three discovery sweeps exist to **deduplicate** — to find what is already covered so the design
does not write it twice. None of them answers a different and equally necessary question: *which
existing flows does this story impose a new rule on?* A story that attaches an invoice to a work
order candidate creates an invariant for every flow that already writes candidates, and none of
those flows' tickets say so, because they were written before the invariant existed.

This sweep finds the candidates for that question. It is the fourth sweep, and it runs **after** the
other three, because one of its branches consumes their output.

Its first consumer is not the human gate. It is the adversarial review at the head of Stage 02's
approval, whose second attack task asks what invariants this story creates — a question answerable
with evidence when this sweep has run and answerable only by guesswork when it has not.

## Evidence, Never Verdicts

**This is the rule the rest of the file exists to protect.** Every entry this sweep returns is
something that *exists*: a flow name, a file path with a line number, an entity name, a test path.
No entry is a judgement — not `affected: true`, not `risk: high`, not "needs regression".

The reason is mechanical. The sweep runs in a subagent, and subagent output varies between runs over
identical inputs. A coverage or risk judgement formed inside the sweep would make the approved set
vary too, and the guarantee would be gone with nothing announcing its departure. So: the sweep
finds, the main run designs, and a human approves.

An entry that says a flow *is* affected has exceeded its mandate, and its result is evidence to be
re-read rather than a conclusion to adopt.

## Branch A — Entity Mutation Traceability

Finds what may break that nothing currently tests. This is the branch that reaches flows nobody has
written a test for, which is where the risk is highest and the existing sweeps are blindest.

1. **Resolve the anchor's primary entity from `ticket.md`.** The navigation path, the requirements
   table, and the acceptance criteria name it between them. A story headed "Candidate Monitoring"
   whose requirements attach invoice data to candidates resolves to `work_order_candidate`.

2. **Find every write operation against that entity** in the frontend source and, where the schema
   is reachable, the API. Record the operation and the path and line where it is declared.

   In the reference repository this is one file, `graphql/work-order-candidate.graphql`, and it
   yields four:

   | Operation | Line |
   |---|---|
   | `UpdateWorkOrderCandidateAmendment` | 111 |
   | `RefreshWorkOrderCandidates` | 123 |
   | `ReassignWorkOrderCandidateVendor` | 211 |
   | `CancelWorkOrderCandidates` | 283 |

3. **Map each operation to the flow that calls it and the screen that flow belongs to.**
   `RefreshWorkOrderCandidates` is the Change Setting flow — the one that removes and regenerates
   candidates, and therefore the one an invoice attachment must survive.

That result is produced from the ticket plus the schema, with no inference about business intent.
The worked example matters for exactly that reason: the flow a human would have had to remember is
reachable mechanically.

## Branch B — Test Inventory

Finds which existing tests a human should re-run. Consumes the Xray list from the second discovery
sweep and the repository `.feature` list from the third, and records those exercising the same
entity or the same screen.

Returns file paths and scenario names. **Never a prediction that a test will fail** — whether it
breaks is what running it determines, and a prediction here would be the verdict this file's
governing rule forbids.

Its output is a Stage 04 regression **recommendation**, not a Stage 03 run scope. Automating those
tests inside the no-stop zone would put work in scope that the stage has no run-state entry, no
attempts budget, and no verdict path for.

## Why The Two Branches Are Not Redundant

They answer different questions and neither subsumes the other:

- Branch A: *what can break that nobody tests?*
- Branch B: *what tests must be re-run?*

A flow both branches return is a stronger candidate than one only a single branch found, and the
merged record keeps both provenances so that strength is visible rather than averaged away.

A third approach — searching by domain vocabulary drawn from the ticket — is deliberately not run.
On a mature project it returns most of the system, which is noise priced as signal.

## Ordering: After The Three, Not Beside Them

The three discovery sweeps share no inputs and no ordering, and run concurrently. **This one does
not.** Branch B consumes the second sweep's Xray list and the third sweep's repository-test list, so
it is sequenced behind both.

Saying so is what keeps the concurrency claim about the other three honest. A fourth sweep quietly
folded into a set described as order-free would make that description false for the whole set.

## Declarations Are Merged With Findings, Never Into Them

A human may declare flows directly. Those declarations and the sweep's findings are kept in
**separate fields**, and each candidate records which produced it: `sweep`, `declared`, or `both`.

Collapsing them into one list would destroy three distinct signals at once — a flow the human knew
about and the sweep confirmed, a flow the sweep found that the human did not think of, and a flow
the human named that the sweep could not reach. The third is the most important of the three,
because it is the one that says the sweep has a blind spot.

## Bounds

This is a read sweep, not a crawl:

- **One hop.** Entity → the operations that write it → the flow that owns each. Not onward to
  entities those flows also touch: two hops from a central entity reaches most of the system.
- **The entity set comes from the ticket, never widened by association.** `work_order_candidate`,
  not also `work_order` because the names look related. A `cross-cutting` design depth permits more
  than one entity; it never permits inferring one.
- **Paths and line numbers, never file contents.** The evidence is the pointer, not the code.
- **A result larger than a page returns the entries and a count of what was truncated.** A silent
  cap reads as a complete answer.
- Design depth scales entity breadth and nothing else. It never scales what the ticket read covers,
  and it never disables a gate.

## When The Sweep Cannot Run

Absent frontend source, an uninitialized submodule, or an entity that cannot be resolved from the
ticket: the sweep records that it did not run, and **why**.

Empty-because-nothing-writes-this-entity and empty-because-the-sweep-could-not-run are different
facts, and every consumer downstream treats them differently. Neither releases the human gate, and
neither excuses the adversarial review: a reviewer with no candidate list still runs, with less
ammunition for the invariants question, and the gate says so.

## Red Flags — thoughts that mean the sweep has exceeded its mandate

| Thought | Reality |
|---|---|
| "This flow obviously breaks, I'll mark it affected" | The sweep records that the flow writes the entity, with the path and line. Whether it breaks is decided later, by a human reading a designed scenario |
| "The human didn't declare it, so it probably doesn't matter" | The human's declarations and the sweep's findings are independent evidence. A finding nobody declared is the case the sweep exists for |
| "The human declared a flow I can't find in the code, I'll drop it" | Record it with `source: declared`. A declaration the sweep cannot reach is the strongest signal available that the sweep has a blind spot |
| "One more hop would find the related entity" | One hop. Two from a central entity returns most of the project as if it were relevant |
| "There are forty candidates, I'll return the ten that look most relevant" | Return them all, or return a page and the count of what was cut. Ranking is a verdict, and picking the interesting ones silently is ranking |
| "No frontend source, so record zero candidates and move on" | Zero-because-nothing-writes-it and zero-because-the-sweep-could-not-run are different facts. Record which one happened, every time |
| "The story is small, so skip the sweep" | Depth scales breadth, never existence. The gate asks its question on every run, and an unrun sweep still has to say it did not run |
