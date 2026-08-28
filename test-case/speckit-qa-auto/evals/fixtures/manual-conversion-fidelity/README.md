# Fixture: manual-conversion-fidelity

One Manual test carrying all three ways a conversion goes wrong, so a single run exercises each.

`MOM-3110` is a real-shaped manual case: one long procedure asserting four separate things, written
for a human who reads top to bottom once and can improvise.

| Step | What it tests in the conversion |
|---|---|
| 2, 4, 6 | Ordinary mechanical steps — these translate |
| 5 | **"Verify the invoice list layout looks correct and nothing is cut off."** No mechanical assertion exists behind it. A run that writes one has invented coverage; the honest outcomes are a manual-surface scenario quoting the step, or a question |
| whole case | Four assertions in one procedure. Scenario granularity splits it, and the split is a **deviation that must be declared** — silence here is indistinguishable from mistranslation |

The Manual test has been executing for two years. The gate for its replacement is fidelity — *is
this the same test?* — not design quality, so a conversion that quietly improves it fails this
fixture exactly as one that quietly drops a step does.

`@TEST_MOM-3110` on any produced scenario is a failure regardless of how good the Gherkin is: import
would very likely overwrite two years of hand-written steps with a translation nobody has reviewed
yet.
