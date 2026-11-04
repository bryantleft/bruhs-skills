---
type: llm
focus: trace
weight: 1
---

PASS if the plan states the authz model for the new audience: a partner_admin role check (requireRole(session, "partner_admin"), following docs/design/2026-02-10-partner-portal-auth.md) on a partner route, rather than loosening requireStaff or exposing the staff-only POST /internal/balances in src/balances/routes.ts to partner admins.

FAIL if the plan reuses or widens the staff endpoint for partners, or names no role check.
