# speckit-qa-auto — Adversarial Review and Impact Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second, independently-scoped review pass to `speckit-qa-auto`'s design stage, plus an impact sweep that finds which existing flows a story creates invariants for — so a story's test design covers the constraints the ticket states outside its acceptance-criteria table, and the regressions the ticket never names.

**Architecture:** No runtime code. This skill is a set of markdown reference files that an agent loads and follows, plus two Python validators that enforce their structure. Work proceeds contract-first: the run-state data shape is edited before any stage that reads it (the contract's own rule 3), and the coupling validator gains check C3 before any file is authored, so every later task is checked as it lands. Stage files are edited in dependency order — shared leaves, then Stage 01, then Stage 02's design half, then its review half, then downstream stages.

**Tech Stack:** Markdown reference files; Python 3.11 stdlib-only validators (`tools/validate_skills.py`, `tools/validate_coupling.py`) with hand-rolled self-tests (`tools/test_validate_*.py`); GitHub Actions (`.github/workflows/validate-skills.yml`).

**Spec:** [`docs/superpowers/specs/2026-08-20-speckit-qa-auto-impact-analysis-design.md`](../specs/2026-08-20-speckit-qa-auto-impact-analysis-design.md)

## Global Constraints

Every task's requirements implicitly include this section.

- **Version:** `speckit-qa-auto` goes `0.2.0` → `0.3.0`. Three places must agree or `validate_skills.py` fails: `speckit-qa-auto/SKILL.md` frontmatter `metadata.version: "0.3.0"`, the skill's own `README.md`, and the root `README.md` skills-table row badge (`v0.3.0`), which `tools/validate_skills.py:292` compares.
- **C1 (enforced):** a file under `references/shared/` links to no other file inside the skill. Shared files are leaves.
- **C2 (enforced):** a file under `references/pipeline/` does not link to another file under `references/pipeline/`. A stage names its successor in prose, never links to it.
- **C3 (added by Task 1):** every markdown link in a `references/pipeline/` file resolves, and every resolved target under `references/shared/` appears on that file's `Loads:` line.
- **Never link outside the skill folder.** `jira-to-speckit` is referred to by name only; a cross-skill link fails `validate_skills.py` and breaks the skill when installed alone.
- **Run-state rule 3:** a field absent from `references/shared/run-state.md` does not travel between stages. Adding one means editing that file first.
- **House style:** every rule in this repository states its reason inline. A rule with no stated reason is rewritten by the next reader who finds it inconvenient. Match the surrounding prose density — these files argue, they do not enumerate.
- **Full check suite** (the "run the tests" step of every task):

  ```bash
  python3 tools/validate_skills.py
  python3 tools/test_validate_skills.py
  python3 tools/validate_coupling.py speckit-qa-auto
  python3 tools/test_validate_coupling.py
  python3 -m compileall -q tools */scripts
  ```

---

### Task 1: Coupling check C3

The spec's loose-coupling claims have never been machine-checked: neither validator verifies that a link resolves or that a loaded leaf is declared. C3 closes that, and it runs first so every file authored in Tasks 2–10 is checked as it lands.

**Files:**
- Modify: `tools/validate_coupling.py` — module docstring, new `LOADS_RE` + `_declared_loads`, new branch in `check_skill`
- Test: `tools/test_validate_coupling.py` — three new tests, two existing fixtures corrected

**Interfaces:**
- Consumes: `relative_links(text)` from `validate_skills` — already imported; returns link targets with code-fenced links stripped.
- Produces: `check_skill(skill_dir) -> list[str]`, unchanged signature. New error strings begin `"{rel}: links to "` and `"{rel}: loads "`.

- [ ] **Step 1: Write the failing tests**

Add to `tools/test_validate_coupling.py`, above `main()`:

```python
def test_pipeline_link_to_missing_file_is_an_error(tmp: Path) -> None:
    skill = build(tmp / "dangling", {
        "SKILL.md": "Router.\n",
        "references/pipeline/stage-01.md":
            "Loads: [run state](../shared/run-state.md).\n\n"
            "See [selectors](../shared/selector-verification.md).\n",
        "references/shared/run-state.md": "Leaf.\n",
    })
    errors = check_skill(skill)
    expect("a pipeline link to a nonexistent file is one error", len(errors) == 1)
    expect("error names the missing target",
           "selector-verification.md" in errors[0] and "does not exist" in errors[0])


def test_undeclared_shared_leaf_is_an_error(tmp: Path) -> None:
    skill = build(tmp / "undeclared", {
        "SKILL.md": "Router.\n",
        "references/pipeline/stage-01.md":
            "Loads: [run state](../shared/run-state.md).\n\n"
            "Then follow [commit](../shared/commit.md).\n",
        "references/shared/run-state.md": "Leaf.\n",
        "references/shared/commit.md": "Leaf.\n",
    })
    errors = check_skill(skill)
    expect("loading an undeclared leaf is one error", len(errors) == 1)
    expect("error names the undeclared leaf and the Loads line",
           "commit.md" in errors[0] and "Loads:" in errors[0])


def test_declared_leaf_on_a_wrapped_loads_line_is_accepted(tmp: Path) -> None:
    skill = build(tmp / "wrapped", {
        "SKILL.md": "Router.\n",
        "references/pipeline/stage-01.md":
            "Loads: [run state](../shared/run-state.md),\n"
            "[commit](../shared/commit.md). Two leaves.\n\n"
            "Body reloads [commit](../shared/commit.md).\n",
        "references/shared/run-state.md": "Leaf.\n",
        "references/shared/commit.md": "Leaf.\n",
    })
    expect("a Loads: line wrapping across lines still declares both leaves",
           check_skill(skill) == [])
```

Register them in `main()`, after `test_stage_may_link_to_a_shared_leaf(tmp)`:

```python
        test_pipeline_link_to_missing_file_is_an_error(tmp)
        test_undeclared_shared_leaf_is_an_error(tmp)
        test_declared_leaf_on_a_wrapped_loads_line_is_accepted(tmp)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 tools/test_validate_coupling.py`
Expected: exit 1, with `FAIL - a pipeline link to a nonexistent file is one error`, `FAIL - loading an undeclared leaf is one error`, and their companion assertions. The third test passes vacuously (no C3 yet, so no errors) — that is expected and is why it is not the only new test.

- [ ] **Step 3: Implement C3**

In `tools/validate_coupling.py`, extend the module docstring's rule list:

```python
  C3  A file under references/pipeline/ links only to files that exist, and
      every shared leaf it links to is named on its `Loads:` line. An
      undeclared leaf is one the reader pays for without being told, and a
      leaf read from memory instead of from the file is one whose field
      names drift.
```

Add after the `PIPELINE` constant:

```python
LOADS_RE = re.compile(r"^Loads:(.*?)(?:\n\n|\Z)", re.S | re.M)


def _declared_loads(path: Path, text: str) -> set[Path]:
    """Resolved paths named on the file's `Loads:` line, which may wrap."""
    match = LOADS_RE.search(text)
    if not match:
        return set()
    return {
        (path.parent / link.split("#", 1)[0].strip()).resolve()
        for link in relative_links(match.group(0))
    }
```

Add `import re` to the import block. Then in `check_skill`, after `text` is read and before the link loop:

```python
        is_pipeline = rel.startswith(PIPELINE + "/")
        declared = _declared_loads(path, text) if is_pipeline else set()
```

and replace the existing `if rel.startswith(SHARED + "/") … elif …` block with:

```python
            if rel.startswith(SHARED + "/"):
                errors.append(
                    f"{rel}: shared files are leaves and must link to nothing "
                    f"inside the skill, but links to {target_rel}"
                )
            elif is_pipeline:
                if target_rel.startswith(PIPELINE + "/"):
                    errors.append(
                        f"{rel}: stage files must not reference each other, "
                        f"but links to {target_rel}"
                    )
                elif not resolved.exists():
                    errors.append(
                        f"{rel}: links to {target_rel}, which does not exist"
                    )
                elif target_rel.startswith(SHARED + "/") and resolved not in declared:
                    errors.append(
                        f"{rel}: loads {target_rel} but does not name it on its "
                        f"`Loads:` line — an undeclared leaf is one the reader "
                        f"pays for without being told"
                    )
```

- [ ] **Step 4: Run the tests — expect three passes and two regressions**

Run: `python3 tools/test_validate_coupling.py`
Expected: the three new checks pass. Two existing checks now FAIL — `clean skill reports no errors` and `a stage may load a shared leaf` — because both fixtures give a pipeline file a link to `../shared/run-state.md` with no `Loads:` line. Those fixtures were under-specified, not wrong: they modelled a stage that loads a leaf without modelling the declaration every real stage carries.

- [ ] **Step 5: Correct the two existing fixtures**

In `test_clean_skill_has_no_errors`:

```python
        "references/pipeline/stage-01.md": "Loads: [run state](../shared/run-state.md).\n",
```

In `test_stage_may_link_to_a_shared_leaf`:

```python
        "references/pipeline/stage-01.md": "Loads: [run state](../shared/run-state.md).\n",
```

- [ ] **Step 6: Run the full check suite**

```bash
python3 tools/test_validate_coupling.py
python3 tools/validate_coupling.py speckit-qa-auto
python3 tools/validate_skills.py
python3 tools/test_validate_skills.py
python3 -m compileall -q tools */scripts
```

Expected: all self-test checks pass; `speckit-qa-auto: ok`. C3 passes on the skill as it stands — verified before this plan was written, across all four stage files: no dangling links, no undeclared leaves. If `speckit-qa-auto: ok` does not appear, stop and report — that means a stage file has an undeclared leaf and the finding belongs to the human, not to a fix here.

- [ ] **Step 7: Add the CI-visible test case row**

In `test-case/speckit-qa-auto/test-cases.md`, add after the `AC10` row:

```markdown
| AC12 | C3 | Pipeline links resolve and are declared | `speckit-qa-auto/` complete | Run `python3 tools/validate_coupling.py speckit-qa-auto` | Output `speckit-qa-auto: ok` — every link in a stage file resolves, and every shared leaf a stage links to is named on that stage's `Loads:` line |
```

- [ ] **Step 8: Commit**

```bash
git add tools/validate_coupling.py tools/test_validate_coupling.py test-case/speckit-qa-auto/test-cases.md
git commit -m "feat(tools): add coupling check C3 for link resolution and Loads declarations

C1 and C2 checked where links may point; neither checked that a link
resolves or that a loaded leaf is declared. The skill's loose-coupling
design has relied on both since it was written.

Two existing fixtures modelled a stage loading a leaf with no Loads:
line, which no real stage does; they are corrected rather than exempted."
```

---

### Task 2: Run-state contract

Run-state rule 3 makes this the first authoring task: a field absent from the contract does not travel between stages, so every later task's fields must exist here first.

**Files:**
- Modify: `speckit-qa-auto/references/shared/run-state.md` — field reference block, rules 9–14

**Interfaces:**
- Produces: `run.design_depth`, `run.depth_raised_in_02`, the whole `impact:` block, `design.adversarial_review`, `design.review_mode`, `design.review_reason`, `design.review_rounds`, and `design.scenarios[].{impact, impact_flow, origin, selector_evidence}`. Tasks 5–8 read these names verbatim; a typo here becomes a field nothing finds.

- [ ] **Step 1: Add the new fields to the `yaml` field reference**

Under `run:`, after `full_suite:`:

```yaml
  design_depth:        trivial | standard | cross-cutting   # resolved in Stage 01
  depth_raised_in_02:  false      # a 2.7b finding raised it after Sweep 4 had run
```

Add a new top-level `impact:` block after the `xray:` block:

```yaml
impact:
  ran:                 true | false
  reason:              ok | no-frontend-source | entity-unresolved | submodule-uninitialized
  entities:            ["work_order_candidate"]
  declared:            ["Change Setting"]        # from --impact; human-authored
  candidates:
    - flow:            RefreshWorkOrderCandidates
      evidence:        "om-mom-frontend/src/graphql/work-order-candidate.graphql:123"
      writes:          work_order_candidate
      existing_tests:  []
      source:          sweep | declared | both
  approved_scenarios:  ["Refreshing candidates does not remove ..."]
  dropped_scenarios:
    - name:            "Cancelling a work order ..."
      reason:          "cancel is blocked upstream for interfaced candidates"
  acknowledged_empty:  false
  sweep_breadth_stale: false
```

Under `design:`, after `selector_evidence:`:

```yaml
  adversarial_review:  approved | issues-fixed | issues-open | not-run
  review_mode:         isolated | inline
  review_reason:       no-subagent-dispatch     # present only when not-run
  review_rounds:       1                        # 0..3
```

And extend the `scenarios:` example with a second entry:

```yaml
    - name:            Refreshing candidates does not remove an invoice-attached candidate
      impact:          true
      impact_flow:     RefreshWorkOrderCandidates
      origin:          extraction | adversarial-review
      dedup:           NEW | REVIEW MOM-5678     # never UPDATE in the impact file
      selector_evidence: source
      status:          pending | green | blocked
      attempts:        0
```

Add `selector_evidence:` to the first `scenarios[]` entry too — it is now per scenario.

- [ ] **Step 2: Amend rule 7 and add rules 9–14**

Rule 7 currently governs a single top-level `selector_evidence`. Append to it:

> The value now lives on each scenario, and the top-level field is the **weakest value present**
> across them. The distinction rule 7 protects is per element — one element resolving from source
> while another needs a live DOM is the ordinary case in a landed run, and a single run-level value
> collapses it. (`deferred` beside `source` is not that case and cannot occur: `source` is written
> only by the Stage 03 entry gate, which never runs at `code_state: pending`, and `deferred` is
> written only at `pending`.)

Then add, after rule 8, the six rules verbatim from spec §2 — rules 9 through 14. Copy their full text; each states its reason, and a rule stripped to its assertion is one the next reader overrules.

- [ ] **Step 3: Verify the contract is self-consistent**

```bash
grep -c "^> \*\*[0-9]\+\." speckit-qa-auto/references/shared/run-state.md
```
Expected: `6` — rules 9–14 present as their own paragraphs. (Rules 1–8 use a numbered list, not blockquotes; do not convert them.)

```bash
grep -n "approved_scenarios\|acknowledged_empty\|review_mode\|design_depth" speckit-qa-auto/references/shared/run-state.md
```
Expected: each name appears in both the yaml block and at least one rule.

- [ ] **Step 4: Run the full check suite**

Expected: `speckit-qa-auto: ok`; `validate_skills.py` reports 0 errors. `run-state.md` is a shared leaf — if C1 fires, a link was added to a file that must have none.

- [ ] **Step 5: Commit**

```bash
git add speckit-qa-auto/references/shared/run-state.md
git commit -m "feat(speckit-qa-auto): add impact and review fields to the run-state contract

Rule 3 makes the contract the first thing edited: a field absent here does
not travel between stages. Adds run.design_depth, the impact block,
design.adversarial_review/review_mode/review_rounds, per-scenario
selector_evidence, and rules 9-14."
```

---

### Task 3: The impact-analysis leaf and the reviewer prompt asset

Two new authored files, both self-contained. `impact-analysis.md` is a shared leaf and must link to nothing (C1). `adversarial-review-prompt.md` is an asset, not a reference file, because it is a template sent verbatim to another agent rather than a document a stage reasons from.

**Files:**
- Create: `speckit-qa-auto/references/shared/impact-analysis.md`
- Create: `speckit-qa-auto/assets/adversarial-review-prompt.md`

**Interfaces:**
- Consumes: `impact.*` field names from Task 2.
- Produces: the Sweep 4 contract Task 5 (Stage 01) executes, and the prompt template Task 7 (Stage 02) dispatches.

- [ ] **Step 1: Write `references/shared/impact-analysis.md`**

Open with the leaf declaration this repo uses:

```markdown
# Shared: Impact Analysis

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.
```

Then the content of spec §1, in this repository's prose register. Required sections, each stating its reason:

1. **Overview** — why a story's own acceptance criteria are not the blast radius, and why the sweep exists to arm a reviewer rather than to reach a verdict.
2. **Evidence, Never Verdicts** — the sweep returns `{flow, evidence, writes, existing_tests, source}` and may not return `affected`, `risk`, or `needs regression`. State the mechanical reason: subagent output varies run to run, and a verdict formed inside a sweep would make the approved set vary too.
3. **Branch A — entity mutation traceability**, with the three numbered steps and the MOM-12194 worked example table (four `work-order-candidate.graphql` operations with line numbers). The worked example is load-bearing: it shows the sweep produces `RefreshWorkOrderCandidates` mechanically, from the ticket plus the schema, with no inference about business intent.
4. **Branch B — test inventory**, consuming sweep 2's Xray list and sweep 3's repo-test list. State that its output is a Stage 04 recommendation, not a Stage 03 run scope.
5. **Ordering** — Sweep 4 runs **after** sweeps 1–3, because Branch B consumes their output. Say plainly that this is why it is not one of the three concurrent sweeps.
6. **Bounds** — one hop; entity set from the ticket, never widened by association; paths and line numbers, never file contents; truncation always counted, because a silent cap reads as a complete answer; `design_depth` scales entity breadth only.
7. **When A Sweep Cannot Run** — `ran: false` with `reason`; empty-because-nothing-writes-this-entity and empty-because-the-sweep-could-not-run are different facts, and neither releases the gate.
8. **Red Flags** table — thoughts that mean the sweep has exceeded its mandate. Model it on `discovery.md`'s. At minimum: "this flow obviously breaks, I'll mark it affected"; "the human didn't declare it so it must not matter"; "one more hop would find the related entity"; "credentials are missing, record zero and move on".

- [ ] **Step 2: Verify the leaf links to nothing**

```bash
grep -nE '\]\([^)]*\.md' speckit-qa-auto/references/shared/impact-analysis.md
```
Expected: no output. Any hit is a C1 violation — reference sibling files by name in prose, never by link.

- [ ] **Step 3: Write `assets/adversarial-review-prompt.md`**

A template, not a document. It must carry, verbatim and in this order:

- The role line and the instruction that the reviewer seeks no further context.
- **Inputs**: `ticket.md`, both `.feature` files, `test-design.md`, `impact-candidates.md`, `run.design_depth` with its reason. State plainly that `test-design.md` carries the extraction's reasoning and that this is accepted — the mechanism rests on the questions asked, not on withholding context.
- **The three attack tasks** for a `story` anchor, worded as spec §5.4 words them, each ending in an instruction to quote the sentence it found.
- **The fidelity task set** for a `test` anchor (spec §7): fidelity, then created invariants when a linked requirement exists.
- **The calibration clause**, verbatim in intent:

  > Only flag issues that would cause real problems. A missing constraint, a contradiction, or a
  > line admitting two readings — those are issues. Wording improvements and stylistic preferences
  > are not. Approve unless there are serious gaps.

  Follow it with the reason, so a future editor does not trim it: an uncalibrated reviewer floods the gate, the human learns to skim, and the mechanism inverts into what it was built to prevent.
- **Output format**: `Approved | Issues Found`; issues as `[Section]: [issue] — [why it matters]`; recommendations advisory and non-blocking; the final message is the whole review, read as data.

- [ ] **Step 4: Run the full check suite**

Expected: `speckit-qa-auto: ok`, 0 errors. `assets/` is permitted by `SKILL_SPEC.md`'s folder layout and is not subject to C1/C2/C3.

- [ ] **Step 5: Commit**

```bash
git add speckit-qa-auto/references/shared/impact-analysis.md speckit-qa-auto/assets/adversarial-review-prompt.md
git commit -m "feat(speckit-qa-auto): add the impact-analysis leaf and the reviewer prompt asset

The leaf specifies Sweep 4: two branches, evidence never verdicts, bounded
at one hop. The prompt is an asset rather than a reference file because it
is sent verbatim to another agent and never reasoned from by a stage."
```

---

### Task 4: Shared leaf edits

Three small, mechanical edits to existing leaves. Folded into one task because a reviewer could not sensibly accept one and reject another: all three are the same change — teaching an existing leaf that a fourth dispatch and a new tag now exist.

**Files:**
- Modify: `speckit-qa-auto/references/shared/discovery.md` — scope the no-ordering claim
- Modify: `speckit-qa-auto/references/shared/host-adaptation.md` — the enumeration
- Modify: `speckit-qa-auto/references/shared/gherkin-conventions.md` — `@IMPACT`

- [ ] **Step 1: Scope `discovery.md`'s ordering claim**

`discovery.md` currently says under "The Three Sweeps": *"Run them concurrently — they share no inputs and no ordering."* That claim is true of sweeps 1–3 and false of Sweep 4, whose Branch B consumes sweeps 2 and 3. Amend the sentence to scope it, and add a short paragraph naming Sweep 4 without linking to it:

```markdown
Run these three concurrently — *these three* share no inputs and no ordering. A fourth sweep,
impact analysis, runs after them and is specified in its own leaf: its test-inventory branch
consumes this file's sweep 2 and sweep 3 output, so it is sequenced, not concurrent. Naming that
dependency here is what keeps the concurrency claim above true rather than nearly true.
```

Reference `impact-analysis.md` by name only — a link would be a C1 violation in a shared leaf.

- [ ] **Step 2: Correct `host-adaptation.md`'s enumeration**

The file says *"Two parts of the pipeline dispatch subagents: discovery's three sweeps, and the selector gate's live-DOM read."* Replace with:

```markdown
Four parts of the pipeline dispatch subagents: discovery's three sweeps, the impact sweep that
follows them, the selector gate's live-DOM read, and the design stage's adversarial review.
```

Leave the degrade-to-inline rule itself **unchanged** — it now covers all four. Append one paragraph explaining why the review is included rather than exempted:

```markdown
The adversarial review was, in an earlier draft, exempted from this rule on the grounds that its
context isolation *was* the capability rather than what inline costs. That exemption is withdrawn.
What makes that review find what self-review cannot is the question it asks — scoped by the ticket
rather than by the extraction's own list of criteria — and a question survives being asked inline.
Isolation is retained as a preference and recorded per run (`design.review_mode`), so its benefit
is measured against real runs rather than asserted. An exemption resting on an unfalsifiable
sentence would let any later step claim the same one, and the rule above would mean nothing.
```

- [ ] **Step 3: Add `@IMPACT` to `gherkin-conventions.md`**

Add a row to the tag table (after the `@TEST_` row):

```markdown
| `@IMPACT` | Feature | Marks a file whose scenarios assert invariants this story imposes on flows other stories own |
```

Then add a paragraph after the table:

```markdown
A file carrying `@IMPACT` may never contain an `UPDATE` row. `UPDATE` carries `@TEST_<TEST-KEY>`,
and importing that tag from inside a file tagged `@REQ_<STORY-KEY>` would update another story's
Test issue in place and move it under this story's requirement. Impact scenarios cover flows other
stories own, so that match is likelier here than anywhere else in the pipeline — a key match in an
impact file is labelled `REVIEW <TEST-key>` and decided by a human.
```

- [ ] **Step 4: Verify**

```bash
grep -n "these three share no inputs" speckit-qa-auto/references/shared/discovery.md
grep -n "Four parts of the pipeline" speckit-qa-auto/references/shared/host-adaptation.md
grep -n "@IMPACT" speckit-qa-auto/references/shared/gherkin-conventions.md
grep -nE '\]\([^)]*\.md' speckit-qa-auto/references/shared/discovery.md speckit-qa-auto/references/shared/host-adaptation.md speckit-qa-auto/references/shared/gherkin-conventions.md
```
Expected: first three each return a line; the fourth returns nothing (no links added to any leaf).

- [ ] **Step 5: Run the full check suite, then commit**

```bash
git add speckit-qa-auto/references/shared/discovery.md speckit-qa-auto/references/shared/host-adaptation.md speckit-qa-auto/references/shared/gherkin-conventions.md
git commit -m "feat(speckit-qa-auto): teach the shared leaves about sweep 4 and @IMPACT

discovery.md's concurrency claim is scoped to the three sweeps it owns,
since sweep 4 consumes two of their outputs. host-adaptation.md counts four
dispatch sites and withdraws the review's exemption from degrade-to-inline.
gherkin-conventions.md gains @IMPACT and the ban on UPDATE inside it."
```

---

### Task 5: Stage 01 — depth resolution and Sweep 4

**Files:**
- Modify: `speckit-qa-auto/references/pipeline/stage-01-intake.md` — `Loads:` line, execution-order block, two new steps, renumbering

**Interfaces:**
- Consumes: `impact-analysis.md` (Task 3), `run.design_depth` and `impact.*` (Task 2).
- Produces: `run.design_depth` and a populated `impact.*` for Stage 02 to read; `impact-candidates.md` on disk in `run.artifact_dir`.

- [ ] **Step 1: Declare the new leaf on the `Loads:` line**

Add `[impact-analysis.md](../shared/impact-analysis.md)` to the `Loads:` line and update the count sentence — it currently reads "Five leaves always, a sixth conditionally". It becomes six always, a seventh conditionally. **C3 fails if the leaf is linked in the body without being declared here**, which is the check Task 1 added.

- [ ] **Step 2: Insert the two steps in the execution-order block**

The block currently ends `… → Jira intake (…) → discovery sweeps → bootstrap (only when no framework) → artifact folder init …`. It becomes:

```
… → Jira intake (fetch → slug → artifact folder → `ticket.md`) → design depth → discovery sweeps
→ impact sweep → bootstrap (only when no framework) → artifact folder init (`execution-report.md`)
+ resume check → Stage 02
```

- [ ] **Step 3: Add step 7 — resolve `run.design_depth`**

Insert between the current step 6 (Jira intake) and step 7 (Discovery sweeps), renumbering the rest. Content: resolve `trivial | standard | cross-cutting` from `ticket.md`, using the spec §5.1 signal table, and record the classification **with its reason**. State why it lives here rather than in Stage 02:

```markdown
Depth is resolved here, not in the stage that uses it, for two reasons. The impact sweep two steps
below scales its entity breadth by this field, and a field resolved after the step that reads it is
the ordering defect design spec §4 already caught once. And reading the whole ticket to classify
costs nothing, because Stage 02 reads all of it at every depth anyway — which is the second half of
the rule: **depth never narrows what gets read.** An earlier draft let `trivial` restrict the read
to the acceptance-criteria table, which is precisely the behaviour that let a stated constraint go
uncovered, re-introduced under a new name and authorized by the very pass that would be audited for
it.
```

- [ ] **Step 4: Add the impact sweep step after the discovery sweeps step**

```markdown
### 8. Impact sweep

Run `impact-analysis.md`'s two branches and write `impact.*` to run state and `impact-candidates.md`
into `run.artifact_dir`.

**This runs after step 7, not alongside it.** Branch B consumes sweep 2's Xray list and sweep 3's
repo-test list, so it is sequenced. The three sweeps above share no inputs; this one does, and
saying so is what keeps that claim honest.

`impact.declared[]` is populated from `--impact` verbatim, unmerged with what the sweep found —
a flow both produced is a cross-confirmation, and a flow only one produced is a different signal
(run-state rule 9). The flag is optional, and its absence answers nothing: the required answer is
taken at the Stage 02 gate, from a human, never inferred from a missing flag.
```

- [ ] **Step 5: Renumber and re-check every internal step reference**

The file cites step numbers in its "Why This Order Is Not The Obvious Order" section and inside later steps. Two insertions shift every step from the old 7 onward by two.

```bash
grep -nE "\bstep [0-9]+\b" speckit-qa-auto/references/pipeline/stage-01-intake.md
```
Read every hit and confirm it names the step it means. This file has been broken by stale step references before — the skill's own history records fixing exactly this after the bootstrap insertion.

- [ ] **Step 6: Run the full check suite, then commit**

Expected: `speckit-qa-auto: ok`. A C3 failure here means step 1 was skipped — the leaf is linked but not declared.

```bash
git add speckit-qa-auto/references/pipeline/stage-01-intake.md
git commit -m "feat(speckit-qa-auto): resolve design depth and run the impact sweep in Stage 01

Depth is resolved before the sweep that scales by it, and never narrows the
read. The impact sweep runs after the three discovery sweeps because its
test-inventory branch consumes two of their outputs."
```

---

### Task 6: Stage 02 — the design half

Splitting Stage 02 across two tasks is deliberate: a reviewer can accept the widened read and the new impact-design step while rejecting how the review loop is bounded, and vice versa.

**Files:**
- Modify: `speckit-qa-auto/references/pipeline/stage-02-test-design.md` — `Loads:` line, "What This Stage Receives", steps 2.1, 2.2, new 2.4b, 2.5, 2.6

**Interfaces:**
- Consumes: `impact.candidates[]`, `impact.declared[]`, `run.design_depth` (Tasks 2, 5); `@IMPACT` and the `UPDATE` ban (Task 4).
- Produces: `<domain>-<aspect>-impact.feature` in `run.artifact_dir`; `design.scenarios[]` entries carrying `impact: true`, `impact_flow`, `origin`; `test-design.md` §2b.

- [ ] **Step 1: Update `Loads:` and "What This Stage Receives"**

The stage reads `impact.*` from run state and `impact-candidates.md` from the artifact folder. Add both to the receives list. Do **not** add `impact-analysis.md` to `Loads:` — Stage 02 does not run the sweep; it reads what Stage 01 left in run state. Adding it would be a leaf the stage pays for and never uses.

- [ ] **Step 2: Generalize step 2.1**

Replace *"Turn `ticket.md`'s acceptance criteria into a list of testable behaviours"* with a whole-ticket read, and state the reason a heading rule was rejected:

```markdown
Turn the **whole ticket** into a list of testable behaviours — every section, at every depth, not
the acceptance-criteria table alone. No rule attaches to any heading name. Headings are how a
writer organized their thoughts, not a schema: a rule keyed to `Out-Scope` patches one ticket
layout and misses the next one that files its constraint under `Notes`.

Which lines are testable constraints is a judgement, and it is the judgement this step has already
got wrong once — a story whose Out-Scope section carried "do not allow user/system modify any
candidate has attached to APM's invoice" produced eight scenarios, none of them that one, and a
coverage matrix reporting no criterion uncovered. The answer is not a stricter rule here. It is the
second question asked at 2.7b, whose scope this step does not set.
```

- [ ] **Step 3: Add the `UPDATE` ban to step 2.2**

```markdown
One exception applies to the impact file designed at 2.4b: a normalized-key match there is labelled
`REVIEW <TEST-key>`, never `UPDATE`. See `gherkin-conventions.md` for why — an `UPDATE` there would
move another story's Test issue under this story's requirement at CI import.
```

- [ ] **Step 4: Add step 2.4b — impact design**

```markdown
### 2.4b Impact design

Design at least one scenario for every entry in `impact.candidates[]`, and for every entry in
`impact.declared[]` the sweep did not find. This is provisional: the human keeps or drops each
scenario at 2.8, and `impact.approved_scenarios[]` records what survived.

Designing before approval, rather than after it, is the whole point of the step's position. In an
earlier draft impact scenarios were authored after the gate — so they passed none of 2.7's checks,
were never seen by the reviewer at 2.7b, were approved by nobody, and were still automated by
Stage 03 and shipped by Stage 04. It also left the reviewer's second attack task with nowhere to
put a finding: a reviewer naming an uncovered invariant had no step to hand it to.

Each scenario states the **invariant**, not the new feature — what must remain true of behaviour
that already existed. `@REQ_<STORY-KEY>` sits at Feature level and `@IMPACT` beside it; the file is
`<domain>-<aspect>-impact.feature`, the main file's name plus `-impact`, derived and never
separately chosen.

**When both lists are empty** — whether the sweep found nothing or could not run — no impact
`.feature` file is written. An empty feature file would be materialized by Stage 03 and imported by
CI as a file containing no tests. The gate's impact section still runs; its content is the sweep's
`ran` and `reason`, and the answer a human still has to give.
```

- [ ] **Step 5: Update steps 2.5 and 2.6**

2.5 writes **both** files. 2.6's `test-design.md` gains **§2b** (impact coverage: candidate → scenario → evidence path → provenance) and **§9** (reserved for the review findings Task 7 writes).

- [ ] **Step 6: Verify**

```bash
grep -n "2.4b" speckit-qa-auto/references/pipeline/stage-02-test-design.md
grep -n "whole ticket" speckit-qa-auto/references/pipeline/stage-02-test-design.md
grep -nE "acceptance criteria into a list" speckit-qa-auto/references/pipeline/stage-02-test-design.md
```
Expected: the first two return lines; the third returns nothing — the old narrow instruction is gone, not merely supplemented.

- [ ] **Step 7: Run the full check suite, then commit**

```bash
git add speckit-qa-auto/references/pipeline/stage-02-test-design.md
git commit -m "feat(speckit-qa-auto): widen 2.1 to the whole ticket and add impact design at 2.4b

2.1 read only the acceptance-criteria table, so a constraint stated
elsewhere in the ticket could not be found by any check downstream. 2.4b
designs impact scenarios before self-review, the reviewer, and the gate,
so all three see them and the reviewer's findings have somewhere to land."
```

---

### Task 7: Stage 02 — the review half

**Files:**
- Modify: `speckit-qa-auto/references/pipeline/stage-02-test-design.md` — step 2.7, new 2.7b, step 2.8, "What This Stage Produces"

**Interfaces:**
- Consumes: `assets/adversarial-review-prompt.md` (Task 3); `design.adversarial_review`, `review_mode`, `review_rounds`, `depth_raised_in_02`, `sweep_breadth_stale` (Task 2); the 2.4b outputs (Task 6).
- Produces: `test-design.md` §9; `impact.approved_scenarios[]` and `impact.dropped_scenarios[]`.

- [ ] **Step 1: Add three checks to step 2.7**

To the existing six:

```markdown
- **No line of the ticket admitted into scope is left with two readings.** The line is resolved to
  one reading, and the resolution is written in `test-design.md` with **both** readings named. A
  line reading either as "this release does not build it" or as "the system must prevent it" is
  exactly the shape that has produced an uncovered constraint here before, and no check looked for
  it.
- Every entry in `impact.candidates[]`, and every unmatched entry in `impact.declared[]`, has at
  least one scenario in the impact file.
- No scenario in the impact file carries `UPDATE`.
```

- [ ] **Step 2: Add step 2.7b — adversarial review**

```markdown
### 2.7b Adversarial review

Dispatch a reviewer with `assets/adversarial-review-prompt.md`, giving it `ticket.md`, both
`.feature` files, `test-design.md`, `impact-candidates.md`, and `run.design_depth` with its reason.

**Why a second pass exists at all.** 2.7 asks *"is every acceptance criterion covered?"* and takes
its list of criteria from the pass being checked. That check is satisfiable while the ticket is
uncovered, because a criterion the extraction never admitted was one is not in the list it
iterates. 2.7b asks *"which sentences in the ticket state a rule the system must uphold?"* — a
question scoped by the ticket rather than by the extraction. **The difference is the question, not
the context.** `test-design.md` states the extraction's boundary in its own opening line, so a
reviewer holding it was never isolated in the way an earlier draft claimed; that draft's exemption
for this step has been withdrawn accordingly.

**Mode.** Prefer a subagent — a fresh context is less anchored on a conclusion it did not reach,
which is a real but unmeasured benefit. Where dispatch is unavailable, run inline with the same
prompt and the same tasks, and record `design.review_mode: inline`. It is never skipped for want of
dispatch: `host-adaptation.md`'s degrade rule covers this step like the other three.

**Loop.** `Issues Found` routes by task — findings from tasks 1 and 3 return to 2.1, findings from
task 2 return to 2.4b — then 2.7 re-runs and the review repeats. Scenarios added carry
`origin: adversarial-review`.

**Bounds.** Every dispatch is one round, whatever caused the re-entry, capped at three — the same
three-strikes bound `operating-rules.md` sets everywhere else. Leaving round three with findings
still open writes `adversarial_review: issues-open`; the open findings go to the gate verbatim and
a human decides. A fourth round would mean the extraction and the reviewer disagree persistently,
which is a question for a person and not for another loop.

A finding that raises `run.design_depth` sets `depth_raised_in_02` and `sweep_breadth_stale`. The
Stage 01 sweep is **not** re-run from here — a stage never reads another stage's reference file —
so the gate reports that the sweep ran at the lower breadth rather than implying a breadth the run
never had.
```

- [ ] **Step 3: Rewrite step 2.8's gate presentation**

Four sections — Depth, Coverage, Review, Impact — as spec §5.5's table gives them. Then:

```markdown
The impact section requires one of three answers: keep a subset of the designed scenarios, keep a
subset plus additions, or state explicitly that no feature is impacted — which writes
`impact.acknowledged_empty: true` and drops them all. **Without one of those three the run does not
continue.** This is the one place in the pipeline where a human's absence of knowledge and a
human's assertion of no impact must not look alike: the sweep returning nothing is not evidence,
and the only thing that can distinguish them is a person saying which it is.

Impact scenarios are presented **unapproved by default**. A pre-checked list converts the human's
job from deciding to noticing, and a reviewer who is only noticing approves everything.

Dropped scenarios are removed from the `.feature` file before commit and kept, with their reasons,
in `impact-candidates.md` and `impact.dropped_scenarios[]` — so the next run over this story does
not re-litigate a decision a human already made, and can see that it was made.
```

Leave the `code_state` × `design_only` next-hop table **unchanged**. Add one sentence beneath it: nothing authors Gherkin after this gate.

- [ ] **Step 4: Extend "What This Stage Produces"**

Add `design.adversarial_review`, `design.review_mode`, `design.review_rounds`,
`impact.approved_scenarios[]`, `impact.dropped_scenarios[]`, `run.depth_raised_in_02`,
`impact.sweep_breadth_stale`.

- [ ] **Step 5: Verify the old red-flag rows do not contradict the new steps**

```bash
grep -n -A 30 "Red Flags" speckit-qa-auto/references/pipeline/stage-02-test-design.md
```
Read every row. Any row implying design ends at 2.7, or that the gate is the last checkpoint before Stage 03, needs the 2.7b step folded in.

- [ ] **Step 6: Run the full check suite, then commit**

```bash
git add speckit-qa-auto/references/pipeline/stage-02-test-design.md
git commit -m "feat(speckit-qa-auto): add adversarial review at 2.7b and rework the gate

2.7's checks take their scope from the pass they check, so no arrangement
of them finds a criterion the extraction never admitted was one. 2.7b asks
a question scoped by the ticket instead. It degrades to inline like every
other dispatch, with the mode recorded so the isolation preference is
measured rather than assumed."
```

---

### Task 8: Stage 03 and Stage 04

**Files:**
- Modify: `speckit-qa-auto/references/pipeline/stage-03-automate.md` — "Run Scope"
- Modify: `speckit-qa-auto/references/pipeline/stage-04-finish.md` — the report

- [ ] **Step 1: Rewrite Stage 03's "Run Scope"**

Keep the existing paragraph and add:

```markdown
The impact file is a second input to **materialization** and generation, and its scenarios get
`design.scenarios[]` entries like any other. The scoped run command covers exactly the scenarios
that have such entries — both files' — and is **not** widened to sweep in pre-existing tests from
the impact flows' domains.

That restraint is not caution, it is arithmetic. This stage's exit condition is a verdict recorded
against every scenario in scope, and its fix loop budgets attempts per entry in
`design.scenarios[]`. A pre-existing test pulled in by a broadened tag filter has no entry, so no
attempts budget and no path to a verdict — inside a no-stop zone that cannot end until every
in-scope scenario has one. Widening the command would manufacture in-scope work this stage has no
mechanism to discharge. Those tests are reported by Stage 04 as recommended regression instead,
where a human can run them.
```

- [ ] **Step 2: Add three report additions to Stage 04**

```markdown
- **Impact scenarios**: each approved one with the flow and evidence path it came from.
- **`design.adversarial_review` and `design.review_mode`.** A run that shipped without a review, or
  with an inline one, says so in the artifact a human reads last — not only in a gate they saw once
  and scrolled past.
- **Recommended regression**: the existing tests Sweep 4's Branch B found for each approved flow.
  This is a list to run or schedule, not a run. Stage 03 deliberately did not execute them, for the
  reason its Run Scope section gives.
```

- [ ] **Step 3: Verify**

```bash
grep -n "not widened\|recommended regression\|Recommended regression" speckit-qa-auto/references/pipeline/stage-03-automate.md speckit-qa-auto/references/pipeline/stage-04-finish.md
```
Expected: hits in both files.

- [ ] **Step 4: Run the full check suite, then commit**

```bash
git add speckit-qa-auto/references/pipeline/stage-03-automate.md speckit-qa-auto/references/pipeline/stage-04-finish.md
git commit -m "feat(speckit-qa-auto): materialize impact scenarios without widening the run command

A pre-existing test pulled into a widened tag filter has no run-state entry,
no attempts budget, and no verdict path inside a no-stop zone. Branch B's
tests become a Stage 04 regression recommendation instead."
```

---

### Task 9: Anchor types, SKILL.md, and the version bump

**Files:**
- Modify: `speckit-qa-auto/SKILL.md` — `--impact`, the leaf inventory, `description`, version
- Modify: `speckit-qa-auto/README.md` — version and the new capabilities
- Modify: `README.md` (repo root) — the skills-table row badge

- [ ] **Step 1: Document the anchor-type matrix**

Spec §7's table belongs in `SKILL.md` beside the existing anchor table, because `--issue` is where the three types are already introduced:

| Anchor | Sweep 4 + depth | 2.7b |
|---|---|---|
| `story` | Once, over the story's entity | Three attack tasks |
| `epic` | Per child | Per child, against that child's files |
| `test` | Over the linked requirement; skipped when none | Fidelity task set |

State why `epic` fans out rather than inventing an epic-level entity: the pipeline already produces one `.feature` per child, and an entity no child's ticket names is one no evidence path can support. State why `test` swaps the task set: attack tasks 1 and 3 have no subject in a conversion — there is no ticket prose to mine and no heading to misclassify — while fidelity (what does the source Manual test assert that the Gherkin does not) is the question that anchor's gate actually turns on.

- [ ] **Step 2: Add `--impact` to Entry Dispatch and Required Inputs**

Parse `--impact "<flow>[, <flow>...]"`. Optional. It populates `impact.declared[]` verbatim and is never merged with sweep output. Say plainly that it is **not** a second entry flag: `--issue` remains required and remains the only anchor.

- [ ] **Step 3: Update the leaf inventory and the Modes section**

Add `impact-analysis.md` to the always-loaded shared list. Note that `assets/adversarial-review-prompt.md` is an asset, not a leaf — it is dispatched, not loaded. In "Modes", add that no flag disables 2.7b or the impact section of the gate, alongside the existing statement that no flag skips a gate.

- [ ] **Step 4: Bump the version in all three places**

```bash
grep -n 'version:' speckit-qa-auto/SKILL.md
grep -rn 'v0\.2\.0\|0\.2\.0' speckit-qa-auto/README.md README.md
```
Set `metadata.version: "0.3.0"` in SKILL.md; update the skill README's version line; update the root README's `speckit-qa-auto` row badge to `v0.3.0`.

Also refresh SKILL.md's `description` — it must still be 40–1024 characters and state what the skill does **and** when to use it. Add the two new capabilities (impact analysis, adversarial design review) without letting it exceed the ceiling.

- [ ] **Step 5: Run the full check suite**

This is the task where a version mismatch surfaces:

```bash
python3 tools/validate_skills.py
```
Expected: `PASS  speckit-qa-auto`, no `root README declares v…` error. That error means step 4 missed the root README, which is a different file from the skill's own.

- [ ] **Step 6: Commit**

```bash
git add speckit-qa-auto/SKILL.md speckit-qa-auto/README.md README.md
git commit -m "feat(speckit-qa-auto): v0.3.0 — --impact flag, anchor-type matrix, new leaf

Defines Sweep 4 and 2.7b for all three anchor types: epic fans out per
child like the .feature output already does, and test swaps the attack
tasks for a fidelity set, since a conversion has no ticket prose to mine."
```

---

### Task 10: Test cases and the E3 fixture

Acceptance criteria split in two, because they are two different kinds of claim. Twenty are deterministic and belong in CI. Four assert that a model pass returns a judgement — one passing run does not distinguish a mechanism from luck, so each runs three times and the **rate** is recorded.

**Files:**
- Modify: `test-case/speckit-qa-auto/test-cases.md`
- Create: `test-case/speckit-qa-auto/fixtures/constraint-under-notes.md`

- [ ] **Step 1: Write the E3 fixture**

A minimal ticket in the shape `jira-to-speckit` produces — frontmatter, description, an acceptance-criteria table, and a section headed **`Notes`** carrying a constraint the AC table does not cover. Model it on the real `mom-12194` `ticket.md` structure so the fixture exercises the same parse path. The constraint must be a genuine prohibition ("the system must not …"), and the AC table must be internally complete without it — otherwise the fixture proves nothing, because a reviewer could find the gap from the AC table alone.

E3 is the case that distinguishes this design from a rule keyed to the word `Out-Scope`. If the mechanism only fires on that heading, E3 fails and the design is what it was accused of being.

- [ ] **Step 2: Add the deterministic rows**

Twenty rows from spec §9.1, in the existing table's column shape (ID / spec item / scenario / preconditions / steps / expected result). Continue the existing `AC` numbering — `AC12` was taken by Task 1, so start at `AC13`. Every row's "Steps" must be a command or a file read, never a judgement.

- [ ] **Step 3: Add the eval-case section**

A separate section below the table, headed so no one mistakes it for a CI gate:

```markdown
## Eval cases — manual, recorded, not CI gates

E1–E4 assert that a model pass returns a judgement. One passing run does not distinguish the
mechanism from luck, so each runs **three times** and the number of runs producing the expected
finding is recorded here. A case that does not reach 3/3 is recorded at its rate, not quietly
dropped — the rate is the evidence this design asked for, and a rate nobody wrote down is a design
decision made by forgetting.
```

Then E1–E4 from spec §9.2, each with its fixture, its expected finding, and a `runs: _/3` field to fill in.

E4 compares E1 run isolated against E1 run inline. State what it is for: the spec retains isolation as a preference rather than a requirement, and E4 is the measurement that would either justify promoting it back to a requirement or confirm it does not matter.

- [ ] **Step 4: Verify**

```bash
python3 tools/validate_skills.py
ls test-case/speckit-qa-auto/fixtures/constraint-under-notes.md
grep -c "^| AC" test-case/speckit-qa-auto/test-cases.md
grep -n "Eval cases" test-case/speckit-qa-auto/test-cases.md
```
Expected: validator passes; fixture exists; the AC row count has grown by 20 over its pre-Task-10 value; the eval section is present.

- [ ] **Step 5: Run the full check suite, then commit**

```bash
git add test-case/speckit-qa-auto/
git commit -m "test(speckit-qa-auto): 20 deterministic cases and 4 recorded eval cases

Four earlier criteria asserted a model pass would return a specific
judgement, which one run cannot establish. They become eval cases run three
times with the rate recorded. The E3 fixture files the same constraint
under a heading named Notes, which is what separates this design from a
rule keyed to Out-Scope."
```

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: §1 → Tasks 3, 5 · §2 → Task 2 · §3 → Tasks 3, 6 · §4 → Task 5 · §5.1–5.2 → Task 6 · §5.3–5.6 → Task 7 · §6 → Tasks 4, 8 · §7 → Task 9 · §8 → Task 1 · §9 → Task 10 · §10–11 → no task (they state what is *not* built). D23–D40 each land in a named task.

**Placeholder scan.** No "TBD", no "add appropriate error handling", no "similar to Task N". Every code step carries the actual code; every markdown step carries the actual prose or names exactly which spec section supplies it and in what register.

**Type consistency.** Field names used downstream match Task 2's contract: `design_depth`, `depth_raised_in_02`, `impact.ran/reason/entities/declared/candidates/approved_scenarios/dropped_scenarios/acknowledged_empty/sweep_breadth_stale`, `design.adversarial_review/review_mode/review_reason/review_rounds`, `scenarios[].impact/impact_flow/origin/selector_evidence`. `check_skill` keeps its signature; `_declared_loads` and `LOADS_RE` are introduced in Task 1 and used nowhere else.

**One known ordering risk.** Task 1 must land before Tasks 3, 5, 6, and 7, or C3 will not be guarding the files that most need it — the ones that gain a new `Loads:` entry. C3 was verified to pass on the skill as it currently stands, so Task 1 cannot be blocked by pre-existing violations.
