# Fixture: constraint-under-notes

The case that separates this design from a rule keyed to the word `Out-Scope`.

The same shape of constraint as `out-scope-constraint`, filed under a heading named **`Notes`**,
among two genuinely non-testable notes:

> A charge that has been included in a settlement must not be re-rated or re-assigned by any user
> or by any scheduled job.

**The acceptance-criteria table is complete without it** — eight rows, every one covered by
`test-design.md`. That completeness is deliberate and load-bearing: if the AC table were internally
incomplete, a reviewer could find the gap from the table alone and the fixture would prove nothing
about reading the whole ticket.

If the mechanism only fires on a heading called `Out-Scope`, E3 fails, and this design is what it
was accused of being.

**Depth**: `cross-cutting`, on the explicit prohibition in Notes.
