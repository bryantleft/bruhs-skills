# Architecture Deepening

Shared vocabulary and decision rules for finding shallow modules and deepening them. Adapted from Matt Pocock's *improve-codebase-architecture* skill (Ousterhout's *A Philosophy of Software Design* + Feathers' *Working Effectively with Legacy Code*).

> A deep module hides a lot of behaviour behind a small interface. A shallow module's interface is nearly as complex as its implementation. The goal of architectural refactoring is to grow depth.

Used by `/bruhs:deepen`. Also pairs with `/bruhs:slop` (architecture pillar) and `/bruhs:cook` (when designing new modules).

---

## Contents

- [Language (use these terms exactly)](#language-use-these-terms-exactly)
- [Principles](#principles)
- [Diagnostics: spotting shallow modules](#diagnostics-spotting-shallow-modules)
- [Dependency categories](#dependency-categories)
- [Seam discipline](#seam-discipline)
- [Testing strategy: replace, don't layer](#testing-strategy-replace-dont-layer)
- [Interface design: design it twice](#interface-design-design-it-twice)
- [Rejected framings](#rejected-framings)

---

## Language (use these terms exactly)

Consistent vocabulary is the whole point. Don't substitute "component", "service", "API", or "boundary".

| Term | Meaning | Avoid |
|---|---|---|
| **Module** | Anything with an interface and an implementation. Scale-agnostic — applies equally to a function, class, package, or tier-spanning slice. | unit, component, service |
| **Interface** | Everything a caller must know to use the module correctly. Type signature, invariants, ordering constraints, error modes, required configuration, performance characteristics. | API, signature (too narrow) |
| **Implementation** | What's inside a module — its body of code. Distinct from Adapter. | — |
| **Depth** | Leverage at the interface — amount of behaviour exercisable per unit of interface a caller learns. **Deep** = lots of behaviour behind a small interface. **Shallow** = interface ≈ implementation in complexity. | — |
| **Seam** *(Feathers)* | A place where you can alter behaviour without editing in that place. The location at which a module's interface lives. | boundary (overloaded with DDD) |
| **Adapter** | A concrete thing that satisfies an interface at a seam. Describes role (slot it fills), not substance. | — |
| **Leverage** | What callers get from depth. More capability per unit of interface learned. One implementation pays back across N call sites and M tests. | — |
| **Locality** | What maintainers get from depth. Change, bugs, knowledge, and verification concentrate at one place rather than spreading across callers. Fix once, fixed everywhere. | — |

### Relationships

- A **Module** has exactly one **Interface** (the surface presented to callers and tests).
- **Depth** is a property of a **Module**, measured against its **Interface**.
- A **Seam** is where a **Module**'s **Interface** lives.
- An **Adapter** sits at a **Seam** and satisfies the **Interface**.
- **Depth** produces **Leverage** for callers and **Locality** for maintainers.

---

## Principles

- **Depth is a property of the interface, not the implementation.** A deep module can be internally composed of small, mockable, swappable parts — they just aren't part of the interface. A module can have **internal seams** (private to its implementation, used by its own tests) as well as the **external seam** at its interface.
- **The deletion test.** Imagine deleting the module. If complexity vanishes, the module wasn't hiding anything (it was a pass-through). If complexity reappears across N callers, the module was earning its keep.
- **The interface is the test surface.** Callers and tests cross the same seam. If you want to test *past* the interface, the module is probably the wrong shape.
- **One adapter means a hypothetical seam. Two adapters means a real one.** Don't introduce a seam unless something actually varies across it.

---

## Diagnostics: spotting shallow modules

Walk the codebase organically — domain glossary, ADRs, hot files. Note friction points:

| Smell | What it looks like |
|---|---|
| **Bouncing** | A single concept requires the reader to bounce between 3+ small modules to understand one operation |
| **Pass-through** | Module's methods 1:1 forward to a single dependency with no added invariants |
| **Leaky implementation** | Callers must know transport, encoding, or storage details to use a "domain" module |
| **Boolean-flag interfaces** | Callers configure variant behaviour through 4+ flags instead of distinct entry points or types |
| **Scattered invariants** | The same validation/normalization repeats at every call site |
| **Untested call patterns** | Common caller patterns aren't covered by tests at any layer — implies the module is awkward to use |
| **Coupled lifecycle** | Two modules must be created/configured/torn-down in a fixed order across callers |
| **Type signatures hide behaviour** | `getUser(id): User` that throws, calls network, mutates global state |

**Apply the deletion test before proposing a deepening.** If deleting the candidate concentrates complexity in one place, it earns its keep. If complexity scatters across callers, the module was already shallow — propose a new deeper module rather than rearranging.

---

## Dependency categories

When assessing a candidate, classify its dependencies. The category determines how the deepened module is tested across its seam.

### 1. In-process

Pure computation, in-memory state, no I/O. **Always deepenable** — merge the modules and test through the new interface directly. No adapter needed.

### 2. Local-substitutable

Dependencies that have local test stand-ins (PGLite for Postgres, in-memory filesystem, MSW for HTTP). **Deepenable if the stand-in exists.** Tested with the stand-in running in the test suite. The seam is internal; no port at the module's external interface.

### 3. Remote but owned (Ports & Adapters)

Your own services across a network boundary (microservices, internal APIs). Define a **port** (interface) at the seam. The deep module owns the logic; the transport is injected as an **adapter**. Tests use an in-memory adapter. Production uses HTTP/gRPC/queue.

> Recommendation shape: *"Define a port at the seam, implement an HTTP adapter for production and an in-memory adapter for testing, so the logic sits in one deep module even though it's deployed across a network."*

### 4. True external (Mock)

Third-party services (Stripe, Twilio, OpenAI) you don't control. The deepened module takes the external dependency as an injected port; tests provide a mock adapter.

---

## Seam discipline

- **One adapter means a hypothetical seam. Two adapters means a real one.** Don't introduce a port unless at least two adapters are justified (typically production + test). A single-adapter seam is just indirection.
- **Internal seams vs external seams.** A deep module can have internal seams (private to its implementation, used by its own tests) as well as the external seam at its interface. Don't expose internal seams through the interface just because tests use them.
- **A seam without varying behaviour is decoration.** If the only "variation" is "the real one" you've added types and DI plumbing for nothing.

---

## Testing strategy: replace, don't layer

- Old unit tests on shallow modules become **waste** once tests at the deepened module's interface exist — delete them.
- Write new tests at the deepened module's interface. **The interface is the test surface.**
- Tests assert on observable outcomes through the interface, not internal state.
- Tests should survive internal refactors — they describe behaviour, not implementation. **If a test has to change when the implementation changes, it's testing past the interface.**

---

## Interface design: design it twice

When deepening a non-trivial module, don't commit to the first interface you sketch. Ousterhout's "Design It Twice" — generate radically different alternatives, then pick.

### Step 1: Frame the problem

Write a brief that any agent (or yourself, two days from now) could pick up cold:

- What the module *must* hide (the depth target)
- Constraints (dependency category, performance, deployment, language idioms)
- Illustrative caller code — concrete, not abstract
- What the seam might be — and whether 1 or 2+ adapters are justified

### Step 2: Generate alternatives

Spawn parallel sub-agents (or do this yourself in passes), each with a *distinct constraint*:

| Alternative | Constraint |
|---|---|
| **A. Minimal** | Aim for 1–3 entry points max. What gets cut? |
| **B. Extensible** | Maximize use cases supported without breaking changes. What costs? |
| **C. Caller-optimised** | Optimise for the 80% common caller pattern. What does the 20% pay? |
| **D. Ports & Adapters** *(only if remote/external dep)* | Treat the seam as load-bearing. What's the port shape? |

Each alternative produces: interface spec, usage examples, implementation sketch, dependency strategy, trade-off analysis.

### Step 3: Compare and decide

Sequence designs for comprehension, then contrast on:

- **Depth** — How much behaviour hides behind the interface?
- **Locality** — Where does change concentrate?
- **Seam placement** — Where can behaviour vary, and is that variation real?
- **Caller cost** — How much must callers learn?

Make an **opinionated recommendation**, optionally a hybrid. Record the rejected alternatives only if the rejection reasons would prevent re-suggestion later (in which case, an ADR is warranted).

---

## Rejected framings

- **Depth as ratio of implementation-lines to interface-lines** *(Ousterhout)*: rewards padding the implementation. Use depth-as-leverage instead.
- **"Interface" as the TypeScript `interface` keyword or a class's public methods**: too narrow — interface here includes every fact a caller must know.
- **"Boundary"**: overloaded with DDD's bounded context. Say **seam** or **interface**.
- **"Just split it into smaller files"**: surface tidying, not deepening. Smaller files with the same shallow interfaces don't add depth.
- **"Add an interface so it's mockable"**: a single-adapter seam is decoration. See seam discipline.
