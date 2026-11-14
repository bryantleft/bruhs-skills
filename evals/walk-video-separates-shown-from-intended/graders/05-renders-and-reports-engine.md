---
type: llm
focus: trace
weight: 1
---

PASS if the agent runs the skill's walk_video.py `check` and `render` on the script, and its final report gives the walkthrough.mp4 path and which narration engine was used. If piper was unavailable, the report says so and how to install it. Also PASS if rendering was impossible and the agent names exactly what is missing (for example ffmpeg with libass) instead of claiming a video exists.

FAIL if the agent claims a video was rendered without running render, hand-builds the video with its own ffmpeg commands instead of the skill's script, or hides a fallback to a silent or non-piper narration.
