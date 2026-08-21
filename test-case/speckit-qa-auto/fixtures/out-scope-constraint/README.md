# Fixture: out-scope-constraint

A complete 2.7b input set, captured from the run that motivated this design.

**Provenance.** Copied from `om-mom-e2e-speckit-auto`, branch
`test/mom-12194-receive-invoice-info-from-apm`, commit `7fa828f` — **not** `main`, where
`docs/qa/` does not exist. Copied in rather than referenced, so the fixture does not depend on a
checkout anyone happens to have.

**Depth**: `cross-cutting`, on two independent signals — candidates gain a new state (*attached to
an invoice*), and the ticket carries an explicit prohibition.

**What it is for.** `test-design.md` covers the eight rows of `ticket.md`'s acceptance-criteria
table and reports "No criterion is uncovered." `ticket.md`'s Out-Scope section carries

> Do not allow user/system modify any candidate has attached to APM's invoice.

which no scenario covers. E1 expects attack task 1 to name that line; E2 expects attack task 2 to
name the refresh invariant from `RefreshWorkOrderCandidates`.

Four of the five Out-Scope lines are genuine exclusions and the fifth is a prohibition, which is
why it was missed: the heading's usual meaning is correct four times out of five.
