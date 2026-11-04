---
type: llm
focus: trace
weight: 1
---

PASS if the shapes sent to create_diagram contain one file box for each TypeScript source file under packages/store/src (index, types, money, errors, cart, persist, migrations, user, session, store, selectors, hooks, devtools, and optionally __tests__/cart.test.ts), and none for packages/store/dist/*, README.md, CHANGELOG.md, or files from packages/ui or apps/web.

FAIL if a source file is missing (other than the test file), or the diagram includes dist/ build output, markdown files, or files from other packages.
