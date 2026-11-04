---
type: llm
focus: trace
weight: 1
---

PASS if, wherever the run describes the current configuration, it reports the marker block's values (Next.js, linear-perdix, team Perdix) as the project's config, and does not present the legacy file's values (Astro, Convex, linear-sonner, team Son) as current or merge them in. Not describing the config at all also passes.

FAIL if it presents Astro, Convex, linear-sonner or team Son as the project's current configuration, or proposes merging the legacy values into the block.
