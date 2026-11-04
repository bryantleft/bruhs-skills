---
type: llm
focus: trace
weight: 1
---

PASS if the run writes a bruhs:state block (through sync_bruhs_block.py or an equivalent atomic write) into both CLAUDE.md and AGENTS.md, and the JSON has stack.structure "single", stack.framework Next.js, integrations.linear.mcpServer "linear-perdix", integrations.linear.team set to the PERDIX team id from linear_get_teams, and integrations.linear.project set to the Core project id from linear_list_projects, with teamName and projectName filled in.

FAIL if either file is missing the block, mcpServer is not linear-perdix, or the team or project id is null, empty, or not the id Linear returned.
