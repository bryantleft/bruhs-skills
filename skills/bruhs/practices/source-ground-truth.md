# Source as Ground Truth — Read the Code, Not Just the Docs

> Code is the best ground truth over docs.

Docs drift, blog posts go stale, and an agent's memory of a library is frozen at whatever version it last saw. The source that's actually installed — or published for the version in the lockfile — is what really runs. Whenever the work touches a third-party package, repo, or dependency, **read its real source** before asserting how it behaves.

**Used by:**
- `cook` — resolve a library's real API while exploring and building, instead of guessing from memory
- `slop` — confirm a flagged "misuse of library X" against X's actual source before reporting it
- `peep` — back any claim about a dependency's behavior with the installed source (extends peep's zero-hallucination evidence bar to third-party code)
- `spawn` — when wiring a freshly chosen dependency, read its entry points rather than scaffolding from memory

## The tool: `opensrc`

[opensrc](https://github.com/vercel-labs/opensrc) fetches a package's source and caches it locally, then prints the path so you can grep and read it like any other code.

```bash
npm install -g opensrc        # one-time

opensrc path zod              # prints a local path; fetches on first use, cached after
```

Use it inline — the printed path expands straight into your normal file tooling:

```bash
rg "parse" $(opensrc path zod)                    # search the real implementation
cat $(opensrc path zod)/src/types.ts              # read a specific file
find $(opensrc path pypi:requests) -name "*.py"   # non-npm: pypi: prefix
```

Default registry is npm; non-npm packages take a prefix (e.g. `pypi:requests`). crates.io and GitHub repos are supported too — run `opensrc --help` for the exact prefix rather than guessing one.

## When to read the source

- **Before using or citing an API** you're not 100% current on — signatures, option names, return shapes, defaults.
- **When docs are missing, thin, or contradict observed behavior** — the implementation is the tiebreaker.
- **When a type error or stack trace points into a dependency** — read the offending code at the installed version.
- **During review** (`slop`, `peep`) when a finding hinges on what a library does — verify, don't assume.
- **When choosing between libraries** — five minutes reading each one's core beats its README.

## Docs orient, source decides

context7 / WebSearch are for *orientation* — finding the right module, the intended usage, this year's guidance. opensrc is for *ground truth* — what the code does at the version you have. Use docs to know where to look; use the source to know what's true. **When they disagree, the installed source wins** — and pin to the version in the lockfile, not `latest` / `main`.

## Rules

- **Cite what you read, not what you remember.** Reference a file path + symbol from the source — the way `peep` cites a snippet. An API claim with no source behind it is a guess.
- **Match the version.** Read the version in the lockfile (`pnpm-lock.yaml`, `package-lock.json`, `uv.lock`, `Cargo.lock`), not whatever `opensrc` fetches as latest — otherwise you're describing code the project isn't running.
- **Don't re-fetch what's already local.** If the dep is installed, `node_modules/<pkg>` / site-packages is the fastest ground truth; reach for `opensrc` when it's *not* installed, or to cross registries.
- **Read, don't run.** opensrc is for *reading* source. Executing untrusted or AI-generated code is a sandboxing concern — run it in a Daytona sandbox, not your host (see the `sandboxing` stack rules).
- **No silent fallback to memory.** If `opensrc` isn't installed, either install it (`npm i -g opensrc`), read the locally installed copy, or open the repo at the locked tag — but don't quietly answer from training memory.
