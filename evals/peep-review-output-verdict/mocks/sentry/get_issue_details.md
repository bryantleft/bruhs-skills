---
---

**Issue BILLING-4F2** (https://acme.sentry.io/issues/4518821/)

Title: InvoiceMismatchError: invoice total does not match tax report
Status: unresolved · Level: error · First seen: 2026-10-14 · Last seen: 2026-11-02 · Events: 312 · Users affected: 41

Message: invoice inv_8812 total 347 != tax report 346 (diff 1 cent)

Tags: service=billing, release=billing@2026.10.28

Breadcrumbs (latest event):
1. GET /invoices/inv_8812
2. buildInvoice lines=3 subtotal=315 tax=32 (tax report: 31)
3. reconcile: tax report rounds once on the subtotal (315 * 0.10 = 31.5, rounded half-up to 32 cents) ... finance export rounded down to 31

Notes from #billing (linked): "The tax report is the source of truth: tax on the subtotal, rounded once half-up. Any per-line rounding will drift by a cent or more on multi-line invoices."
