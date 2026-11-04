---
type: llm
focus: trace
weight: 1
---

PASS if the run gives a state for each of the 8 layers and concludes most are healthy: acceptance specs gated (acceptance job), unit tests present, coverage gated at 85% on changed lines, mutation runner scheduled weekly with a ratchet, architecture checker gated (check_deps.sh + dependency-rules.json), test-code linter present (clippy --all-targets covers tests), CI orchestrator gated with no continue-on-error, and complexity composite absent.

FAIL if a layer is missing from the map, or a healthy layer is reported as absent or advisory (for example the test-code linter called absent, or the orchestrator called advisory).
