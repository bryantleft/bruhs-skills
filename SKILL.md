---
name: bruhs
description: Opinionated development lifecycle - spawn projects, cook features, yeet to ship
---

# bruhs - Complete Development Lifecycle

When invoked, ask the user which command to run:

```
What do you want to do?
○ spawn - Create new project or add to monorepo
○ cook - Plan + Build a feature end-to-end
○ yeet - Ship: Linear ticket → Branch → Commit → PR
```

Use AskUserQuestion to present these options, then follow the corresponding command file:
- **spawn** → Read and follow `commands/spawn.md`
- **cook** → Read and follow `commands/cook.md`
- **yeet** → Read and follow `commands/yeet.md`

## Quick Access

Users can also specify directly:
- `/bruhs spawn` or `/bruhs spawn <name>`
- `/bruhs cook` or `/bruhs cook <feature>`
- `/bruhs yeet`

If an argument is provided, skip the selection and go directly to that command.
