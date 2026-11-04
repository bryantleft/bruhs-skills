---
type: llm
focus: trace
weight: 1
---

PASS if the run recognizes that CLAUDE.md has no bruhs:state block but a legacy .claude/bruhs.json exists (the Case B migration path), and takes the Migrate option the user already asked for. Note that read_bruhs_block.py --kind state prints the legacy file's JSON when no block exists, so seeing JSON from it does not mean a marker block exists.

FAIL if it treats the project as already configured with a marker block (offering to reconfigure), or as unconfigured (fresh setup that ignores the legacy file).
