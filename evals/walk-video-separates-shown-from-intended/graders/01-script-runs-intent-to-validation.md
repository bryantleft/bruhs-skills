---
type: llm
focus: { source: file, path: .git/bruhs/walk/pr-42/script.json }
weight: 1
---

This file is the video walkthrough script the agent wrote for PR #42.

PASS if it is a JSON object whose "scenes" start with an "intent" scene that says why the PR exists (the documented 100 requests per minute search quota was not enforced), include at least one "change" scene about the limiter or its wiring into /v1/search, and end with a single "validation" scene whose visual is {"type": "claims"}, in intent → change → implications → validation order.

FAIL if the file is missing or not JSON, the first scene is not about intent, there is no change scene, or the last scene is not the validation scene.
