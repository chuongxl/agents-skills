# Impact candidates — FIX-0001

Sweep: `ran: true`, `reason: ok`. Entity: `charge`.
Declared by the human (`--impact`): none.

| Flow | Evidence | Writes | Existing tests | Source |
|---|---|---|---|---|
| `ReRateCharges` | `src/graphql/charge.graphql:88` | `charge` | `src/tests/billing/charge-rerate.feature` | sweep |
| `ReassignChargeOwner` | `src/graphql/charge.graphql:141` | `charge` | — | sweep |
| `NightlyChargeRecalculationJob` | `src/jobs/charge-recalculation.ts:34` | `charge` | — | sweep |

No decisions recorded — this fixture captures the state at the moment 2.7b is dispatched.
