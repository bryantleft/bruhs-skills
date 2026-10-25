#!/usr/bin/env bash
# Reference polish: one spacing scale and type ramp, light and dark themes, a single-column
# layout under 600px (no fixed widths), visible :focus-visible rings, labelled fields,
# named icon buttons, real switches (button role=switch), distinct destructive action and
# save feedback. Runs in the workspace; $REFERENCE_DIR is this dir.
set -euo pipefail
cp -R "$REFERENCE_DIR/files/." .
