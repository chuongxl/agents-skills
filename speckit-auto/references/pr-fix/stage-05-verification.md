# PR fix: Stage 05 verification

When there is no matching spec, pass the PR description, fix request and actual changed paths
in place of spec/plan to the verification skill, and assess evidence against the requested behavior
rather than inventing spec criteria. Report unavailable or unexercised behavior honestly.
For an investigation or mismatch, return through the PR-fix Stage 02/03 routes as applicable;
repeat direct review when no matching spec exists, not `speckit-code-review`.
