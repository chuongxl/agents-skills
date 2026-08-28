# Xray manual and generic tests covering MOM-12401

| Key | Type | Summary | Steps (verbatim) |
|---|---|---|---|
| MOM-3042 | Manual | Vendor audit trail records a rejected assignment | 1. Open a work order with no vendor assigned.<br>2. Attempt to assign a vendor whose compliance certificate has lapsed.<br>3. Confirm the assignment is refused.<br>4. Open Vendor > Audit trail and confirm a new entry exists for the refused assignment, with the acting user and timestamp. |
