# Impact candidates — MOM-12194

Sweep: `ran: true`, `reason: ok`. Entity: `work_order_candidate`.
Declared by the human (`--impact`): none.

| Flow | Evidence | Writes | Existing tests | Source |
|---|---|---|---|---|
| `RefreshWorkOrderCandidates` | `om-mom-frontend/src/graphql/work-order-candidate.graphql:123` | `work_order_candidate` | — | sweep |
| `CancelWorkOrderCandidates` | `om-mom-frontend/src/graphql/work-order-candidate.graphql:283` | `work_order_candidate` | — | sweep |
| `UpdateWorkOrderCandidateAmendment` | `om-mom-frontend/src/graphql/work-order-candidate.graphql:111` | `work_order_candidate` | — | sweep |
| `ReassignWorkOrderCandidateVendor` | `om-mom-frontend/src/graphql/work-order-candidate.graphql:211` | `work_order_candidate` | — | sweep |

No decisions recorded — this fixture captures the state at the moment 2.7b is dispatched.
