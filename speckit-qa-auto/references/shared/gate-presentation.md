# Shared: Gate Presentation

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## Overview

Every other file in this skill describes what the pipeline **decides**. This one describes what it
**says to a person**, and it is the only file that does. Stages hold a strong internal contract —
fixed field names, mechanically produced dedup labels, a one-way depth ratchet, numbered steps — and
all of it is load-bearing. None of it is the user's to learn.

Without a file owning this boundary, each gate invents its own presentation, and an invented
presentation reverts to reciting the contract, because the contract is what the stage file is made
of. That is not hypothetical: a real run presented a human with

> `Test approach for MOM-12634 (design_depth: cross-cutting, three alternatives as required)`

— a step's own governing rule, quoted at a reader who has no rule book, with a field name attached.
The QA team that received it reported it as unreadable, and they were right.

## The Rules

**1. One question per message.** A topic needing more exploration becomes more messages, never a
compound question. Two questions in one message means the second one gets the answer to the first.

**2. The number of questions is never capped.** Ask as many as there are real concerns. Nothing in
this pipeline — depth, mode, anchor type — reduces how many questions may be asked; a cap does not
remove concerns, it converts them into silent assumptions, because the run must continue and the
ticket will not answer them on its own.

**A concern not asked is written down.** Any assumption made in place of a question goes to Open
Questions in `test-design.md`. Not asking is permitted. Not asking silently is not.

**3. Alternatives are carried by the choices, never folded into the question, and the recommendation
comes first.** Where the host offers structured options, each option is one alternative — its label
naming the choice, its description carrying the trade-off. Where the host offers none, the
alternatives are a labelled list beneath a one-sentence question. **The shape degrades; the contract
does not.** An option that only says *approve* or *I disagree* is an acknowledgement, not an
alternative, and it means the alternatives are in the wrong place.

**4. Sections are presented one at a time**, and each asks whether it looks right before the next
begins. A gate with five sections delivered in one block is a gate whose later sections are skimmed.
Sections that only report may be grouped into one message; a section carrying a decision stands
alone.

**5. Nothing a person reads names a stage, a run-state field, or a rule.** Not step numbers (`2.1`,
`2.2b`, `stage 04`), not field names (`design_depth`, `dedup`, `approach_chosen`,
`selector_evidence`), not clauses restating this skill's own constraints (*"three alternatives as
required"*, *"per the depth table"*). No replacement marker is introduced either: the question
stands on its own, and the pipeline's shape is not the reader's to track.

Labels that must appear in a table a person reads are rendered in plain words — `SKIP MOM-5678`
reads as *already covered by MOM-5678*, `REVIEW-OVERLAP MOM-5678` as *overlaps an existing test,
needs a look*. **This is a rendering rule only.** The stored value never changes, because the
mechanical vocabulary is what makes two runs over unchanged inputs agree.

**6. An internal label with no consequence a person can act on is not presented at all.** Where a
classification does have a consequence, it travels as that consequence in plain words — *"I'll check
four related areas and write a fuller design document"* — never as the label. Where it has none,
presenting it costs a turn and returns a guess. `run.design_depth` is the standing example: it
scales sweep breadth, document verbosity, and how many approaches a gate offers, none of which a
reader can see. It is resolved internally and never shown.

## Red Flags — thoughts that mean a gate is about to recite the contract

| Thought | Reality |
|---|---|
| "I'll name the step so they know where we are" | They do not track the pipeline's shape, and it is not their job to. The question stands alone |
| "Stating the rule shows I'm following it" | *"three alternatives as required"* tells a reader they are watching a machine satisfy itself. Present the three alternatives; say nothing about being required to |
| "The depth is cross-cutting, they should know that" | They cannot act on it. If a wider sweep changes what they get, say what they get |
| "All three approaches fit in the question, the options can just confirm" | Then the options carry acknowledgements and the alternatives are unreadable. One option per alternative |
| "There's no structured question tool on this host, so prose it is" | Prose keeps the contract: one sentence asking, a labelled list of alternatives, recommendation first |
| "Depth is trivial, so one question is enough" | Depth never bounds questions. Ask what there is to ask, or write the assumption into Open Questions |
| "I'll present all five sections together, it's one gate" | It is one gate and five reads. Decisions stand alone |
| "This label has no plain-word form, I'll show it raw" | A label with no plain-word form has no consequence a reader can act on, which means it is not shown |
