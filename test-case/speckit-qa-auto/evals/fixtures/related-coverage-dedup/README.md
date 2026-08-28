# Fixture: related-coverage-dedup

The case that separates a run reading `--related` exports from one that does not.

MOM-12500 is a new story. **Nothing is linked to it in Xray**, so `existing-tests.feature` is empty
— which is the normal state of a story on a project whose automation trails its manual suite, and
the state in which dedup computed against that file alone labels everything `NEW`.

The coverage that matters is on two sibling stories in the same flow, exported here through
`--related`:

- `existing-tests-MOM-12401.feature` already covers rejecting an expired vendor certificate. The
  MOM-12500 acceptance criteria restate that behaviour, so any reasonable design writes it again.
- `existing-tests-MOM-12401-manual.md` covers the audit-trail entry as a Manual test. The dedup
  script cannot parse it, so a run that reports labels straight from the script output will call it
  `NEW` while a human who read the manual table would not.

A run that passes only `existing-tests.feature` to the script reports two duplicates as new work.
That is the failure this fixture exists to catch, and it fails silently — an all-`NEW` result looks
exactly like a genuinely uncovered story.
