---
tags: [deepen]
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write, Edit]
---

/bruhs:deepen ReservationManager --no-explore

I won't be around to answer questions, so make the calls yourself: pick the design you'd recommend and give me the full hand-off. One thing I already know: we tried pulling deposits out into their own service last year and backed it out, because a deposit and its reservation have to commit in the same transaction. Don't propose that again, and make sure the next person doesn't either.
