# Xray manual and generic tests covering MOM-12550

| Key | Type | Summary | Steps (verbatim) |
|---|---|---|---|
| MOM-3110 | Manual | Invoice list — filter, sort and open | 1. Log in as a user with the Finance role.<br>2. Open Invoices > All invoices and confirm the list loads with the default filter set to This month.<br>3. Set the status filter to Rejected and confirm only rejected invoices are listed.<br>4. Sort by Invoice date descending and confirm the newest invoice is first.<br>5. Verify the invoice list layout looks correct and nothing is cut off.<br>6. Open the first invoice and confirm the invoice detail page shows the same invoice number as the row that was clicked. |
