# Rust Best Practices

Idiomatic modern Rust (2024 edition). Organized around Rust's mental model: ownership first, errors as values, types as proofs.

**Used by:**
- `cook` - Patterns to follow when building features
- `slop` - Patterns to detect and fix during cleanup

**Stack triggers:** `framework: rust|leptos|axum|tauri|gpui` or `language: rust` in `bruhs.json`.

## Contents

- [Mental Model](#mental-model)
- [Pillar 1: Ownership & Borrowing](#pillar-1-ownership--borrowing)
- [Pillar 2: Errors as Values](#pillar-2-errors-as-values)
- [Pillar 3: Type System Discipline](#pillar-3-type-system-discipline)
- [Pillar 4: Iterator-First](#pillar-4-iterator-first)
- [Pillar 5: Async Boundaries](#pillar-5-async-boundaries)
- [Pillar 6: Modules & Workspace](#pillar-6-modules--workspace)
- [Pillar 7: Tooling Discipline](#pillar-7-tooling-discipline)
- [Pillar 8: Comments & Docs](#pillar-8-comments--docs)
- [Frameworks](#frameworks)
- [Quick Reference Checklist](#quick-reference-checklist)
- [Performance](#performance)

---

## Mental Model

> **Ownership is the primary lens. Types are proofs. Errors are values. Async is colored.**

In TypeScript you reach for the type system first. In Rust you reach for **ownership** first — every value has exactly one owner, and lifetimes flow from that. Types come second (newtypes, typestate, exhaustive enums). Errors are returned, never thrown. Async is a property of the function signature you must thread through.

If you find yourself wrestling the borrow checker, the design is usually wrong, not the code. Step back and ask: *who owns this data?*

---

## Pillar 1: Ownership & Borrowing

> **Borrow by default. Clone deliberately. Own only when you must.**

### DO: Borrow in function signatures

```rust
// ✅ Borrow — caller keeps ownership, no allocation
fn greet(name: &str) {
    println!("Hello {name}");
}

// ✅ Slice — works for Vec<T>, [T; N], and &[T]
fn sum(values: &[u32]) -> u32 {
    values.iter().sum()
}

// ✅ Take ownership only when you store, transform-and-return, or send across threads
fn store(name: String, store: &mut Vec<String>) {
    store.push(name);
}
```

### DON'T: Owned types in arguments by default

```rust
// ❌ Forces caller to allocate or clone
fn greet(name: String) { /* ... */ }

// ❌ &Vec<T> / &String — extra indirection, accept slices instead
fn sum(values: &Vec<u32>) -> u32 { /* ... */ }
fn greet(name: &String) { /* ... */ }
```

### Clone Decision Tree

| Situation | Use |
|-----------|-----|
| Need to mutate AND keep original | `.clone()` |
| Shared immutable across threads | `Arc<T>` (clone the `Arc`, not `T`) |
| Shared immutable single-threaded | `Rc<T>` |
| Ownership ambiguous (sometimes borrow, sometimes own) | `Cow<'_, T>` |
| Small `Copy` type (≤ 24 bytes, no heap) | Pass by value |
| Need ownership in async task | `.clone()` *before* `tokio::spawn` |

### Clone Anti-Patterns

```rust
// ❌ Cloning inside iterator
let names: Vec<String> = users.iter().map(|u| u.name.clone()).collect();

// ✅ Use .cloned() or .iter().map(...) returning &str
let names: Vec<&str> = users.iter().map(|u| u.name.as_str()).collect();

// ❌ Cloning to "fix" a borrow error
fn process(data: &Data) {
    let owned = data.clone();  // probably wrong
    helper(owned);
}

// ✅ Pass the borrow through
fn process(data: &Data) {
    helper(data);
}
```

### Copy Threshold

Derive `Copy` when **all fields are `Copy`** AND the struct is **≤ 24 bytes** (≤ 3 words on 64-bit) AND it has **no heap allocations**.

```rust
// ✅ Good Copy candidate
#[derive(Debug, Copy, Clone)]
struct Point3 { x: f32, y: f32, z: f32 }  // 12 bytes

// ❌ Bad — String is not Copy
#[derive(Clone)]  // Clone yes, Copy no
struct User { id: u64, name: String }
```

For full ownership patterns → `rust-ownership-and-borrowing.md`

---

## Pillar 2: Errors as Values

> **Return `Result`. Never `unwrap()` outside tests. `thiserror` for libs, `anyhow` for binaries only.**

### DO: Return `Result<T, E>` for fallible operations

```rust
// ✅ Crate-level error enum with thiserror
#[derive(Debug, thiserror::Error)]
pub enum ParseError {
    #[error("empty input")]
    Empty,
    #[error("invalid number at byte {position}")]
    InvalidNumber { position: usize },
    #[error(transparent)]
    Io(#[from] std::io::Error),
}

pub fn parse(input: &str) -> Result<u64, ParseError> {
    if input.is_empty() {
        return Err(ParseError::Empty);
    }
    input.parse().map_err(|_| ParseError::InvalidNumber { position: 0 })
}
```

### DO: Use `?` to bubble errors

```rust
// ✅ Flat, readable, errors propagate via ?
fn handle(req: &Request) -> Result<Response, ServiceError> {
    let validated = validate(req)?;
    let user = lookup_user(validated.id)?;
    let body = render(user)?;
    Ok(Response::ok(body))
}
```

### DON'T: `unwrap()`, `expect()`, or `panic!()` in production

```rust
// ❌ Panics on missing config
let port = config.port.unwrap();

// ❌ Panics on missing env var
let url = std::env::var("DATABASE_URL").expect("DATABASE_URL not set");

// ✅ Surface the error
let port = config.port.ok_or(ConfigError::MissingPort)?;
let url = std::env::var("DATABASE_URL").map_err(|_| ConfigError::MissingDatabaseUrl)?;
```

**`unwrap()`/`expect()` are acceptable in:**
- Tests, benches, examples
- `const`/`static` initialization where failure is a build error
- After a check that proves the invariant (use `let ... else { unreachable!() }` instead)

### `let ... else` over nested matches

```rust
// ✅ Early exit when None is expected
let Some(user) = find_user(id) else {
    return Err(MyError::UserNotFound(id));
};

// ✅ Early exit in a loop
for entry in entries {
    let Ok(parsed) = parse(entry) else { continue };
    process(parsed);
}
```

### Library vs Binary Error Choice

| Crate type | Use | Why |
|-----------|-----|-----|
| Library | `thiserror` enums | Callers can match on variants |
| Binary (CLI/server) | `anyhow::Result` at the edges | Ergonomic context with `.context("...")` |
| Test helpers | `anyhow` or `Box<dyn Error>` | Throwaway error type is fine |

```rust
// ❌ anyhow in a library — erases callers' ability to handle errors
pub fn fetch(url: &str) -> anyhow::Result<Data> { /* ... */ }

// ✅ Concrete error in a library
pub fn fetch(url: &str) -> Result<Data, FetchError> { /* ... */ }
```

For full error patterns → `rust-error-design.md`

---

## Pillar 3: Type System Discipline

> **Make illegal states unrepresentable. Newtypes for meaning. Typestate for protocols.**

### DO: Newtype primitives that have meaning

```rust
// ❌ All u64s look the same — easy to swap arguments
fn transfer(from: u64, to: u64, amount: u64) -> Result<(), Error>

// ✅ Newtypes catch swaps at compile time
#[derive(Debug, Copy, Clone, PartialEq, Eq, Hash)]
pub struct UserId(u64);

#[derive(Debug, Copy, Clone, PartialEq, Eq)]
pub struct Cents(u64);

fn transfer(from: UserId, to: UserId, amount: Cents) -> Result<(), Error>
```

### DO: Exhaustive enums over flag soup

```rust
// ❌ Multiple booleans = impossible states are representable
struct Job {
    is_pending: bool,
    is_running: bool,
    is_done: bool,
    result: Option<Output>,
}

// ✅ Enum where each variant carries exactly the data it needs
enum Job {
    Pending,
    Running { started_at: Instant },
    Done(Output),
    Failed(JobError),
}
```

### DO: Use stdlib invariant types

```rust
// ✅ Compiler enforces non-zero
use std::num::NonZeroU32;
fn page_size(n: NonZeroU32) -> Vec<Item> { /* ... */ }

// ✅ Compiler enforces non-empty path
use std::path::Path;
fn open(path: &Path) -> Result<File, Error> { /* ... */ }
```

### Typestate Pattern

Encode protocol state in the type. Illegal transitions become compile errors.

```rust
struct Connection<S> {
    socket: TcpStream,
    _state: PhantomData<S>,
}

struct Disconnected;
struct Connected;

impl Connection<Disconnected> {
    fn open(addr: &str) -> io::Result<Connection<Connected>> { /* ... */ }
}

impl Connection<Connected> {
    fn send(&mut self, msg: &[u8]) -> io::Result<()> { /* ... */ }
    fn close(self) -> Connection<Disconnected> { /* ... */ }
}

// ❌ Compile error: send() doesn't exist for Connection<Disconnected>
let conn = Connection::<Disconnected>::open("...")?;
conn.send(b"data");  // works only if `open` returned Connected
```

For full type discipline → `rust-type-state-and-newtypes.md`

---

## Pillar 4: Iterator-First

> **Lazy chains over manual loops. `for` only when you need early exit.**

### DO: Chain iterator combinators

```rust
// ✅ Fused into one loop at compile time, zero allocations until .collect()
let active_emails: Vec<&str> = users
    .iter()
    .filter(|u| u.is_active)
    .map(|u| u.email.as_str())
    .collect();

// ✅ Aggregate without allocating
let total: u64 = orders.iter().map(|o| o.amount).sum();
```

### DON'T: Allocate intermediate collections

```rust
// ❌ Unnecessary Vec — clippy::needless_collect
let names: Vec<_> = users.iter().map(|u| &u.name).collect();
for name in names { println!("{name}"); }

// ✅ Iterate directly
for user in &users {
    println!("{}", user.name);
}
```

### When `for` loops win

Prefer `for` when you need:
- Early exit (`break`, `continue`, `return`)
- Side effects with cleanup
- The code reads better than a 4-stage iterator chain

```rust
// ✅ for is right here — early exit
for line in reader.lines() {
    let line = line?;
    if line.starts_with("END") { break; }
    process(&line)?;
}
```

### Pick the right consumer

| You want | Use |
|----------|-----|
| Sum | `.sum()` (specialized; faster than `.fold(0, |a, b| a + b)`) |
| Min/max | `.min()` / `.max()` |
| First match | `.find(...)` (short-circuits) |
| Any/all | `.any(...)` / `.all(...)` (short-circuit) |
| Group/aggregate | `itertools::Itertools::chunk_by` or fold |

---

## Pillar 5: Async Boundaries

> **`Send + Sync + 'static` infects everything. No blocking in `async fn`. Cancel safely.**

### DO: Mind the bounds

```rust
// ✅ tokio::spawn requires Send + 'static
let handle = tokio::spawn(async move {
    let data = fetch().await?;
    process(data).await
});
```

### DON'T: Block in async code

```rust
// ❌ Blocks the runtime worker thread
async fn read_config() -> Result<Config, Error> {
    let bytes = std::fs::read("config.toml")?;  // sync I/O
    parse(&bytes)
}

// ✅ Async I/O
async fn read_config() -> Result<Config, Error> {
    let bytes = tokio::fs::read("config.toml").await?;
    parse(&bytes)
}

// ✅ Or move CPU-bound work off the runtime
async fn hash(data: Vec<u8>) -> [u8; 32] {
    tokio::task::spawn_blocking(move || expensive_hash(&data))
        .await
        .expect("hash task panicked")
}
```

### DON'T: Hold locks across `.await`

```rust
// ❌ Deadlock risk — blocks the worker, can deadlock with self
async fn bad(state: Arc<Mutex<State>>) {
    let guard = state.lock().unwrap();
    fetch_remote(&guard.url).await;  // .await while holding sync lock
}

// ✅ Drop the lock before awaiting
async fn good(state: Arc<Mutex<State>>) {
    let url = {
        let guard = state.lock().unwrap();
        guard.url.clone()
    };
    fetch_remote(&url).await;
}

// ✅ Or use tokio::sync::Mutex when you must hold across await
async fn also_good(state: Arc<tokio::sync::Mutex<State>>) {
    let guard = state.lock().await;
    fetch_remote(&guard.url).await;
}
```

For full async patterns → `rust-async-patterns.md`

---

## Pillar 6: Modules & Workspace

### DO: Keep `pub` discipline

```rust
// lib.rs
pub mod api;        // public surface
pub(crate) mod db;  // visible to crate, not external
mod internal;       // private

// Re-export the curated public API at the crate root
pub use api::{Client, ClientBuilder, ClientError};
```

### DO: Use workspace lints (Rust 1.74+)

```toml
# Workspace Cargo.toml
[workspace.lints.rust]
unsafe_code = "deny"
missing_docs = "warn"

[workspace.lints.clippy]
all = { level = "deny", priority = -1 }
pedantic = { level = "warn", priority = -1 }
unwrap_used = "deny"
expect_used = "warn"
```

```toml
# Each member Cargo.toml
[lints]
workspace = true
```

### Feature flags should be additive

```toml
[features]
default = ["tokio"]
tokio = ["dep:tokio"]
async-std = ["dep:async-std"]
# ❌ Don't make features mutually exclusive — breaks `cargo check --all-features`
```

---

## Pillar 7: Tooling Discipline

### Always run

```shell
cargo fmt --all
cargo clippy --all-targets --all-features --locked -- -D warnings
cargo test --all-features --workspace
```

### Suppress lints with `#[expect]`, not `#[allow]`

```rust
// ✅ Will warn if the lint stops applying — keeps the codebase honest
#[expect(clippy::large_enum_variant, reason = "matching speed > size")]
enum Message {
    Code(u8),
    Content([u8; 1024]),
}

// ❌ Stays silent forever even if the warning becomes wrong
#[allow(clippy::large_enum_variant)]
enum Message { /* ... */ }
```

### Import order (`rustfmt.toml`)

```toml
reorder_imports = true
imports_granularity = "Crate"
group_imports = "StdExternalCrate"
```

Produces:
```rust
use std::sync::Arc;

use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;

use crate::error::Error;
```

---

## Pillar 8: Comments & Docs

### `///` for public APIs

```rust
/// Fetches the user with the given ID.
///
/// # Errors
///
/// Returns [`Error::NotFound`] if no user exists with the given ID.
/// Returns [`Error::Database`] if the underlying query fails.
///
/// # Examples
///
/// ```
/// # use mycrate::{get_user, UserId};
/// let user = get_user(UserId::new(42))?;
/// assert_eq!(user.name, "Alice");
/// # Ok::<(), mycrate::Error>(())
/// ```
pub fn get_user(id: UserId) -> Result<User, Error> { /* ... */ }
```

### `//` for the WHY, not the WHAT

```rust
// ✅ Explains a non-obvious decision
// PERF: BTreeMap here because we iterate in sorted order on every render.
let entries: BTreeMap<Key, Value> = build_index();

// ✅ Mandatory on unsafe
// SAFETY: `ptr` is non-null and properly aligned (checked above on line 42).
// The buffer is valid for `len` bytes and we hold exclusive access.
unsafe { ptr::write_bytes(ptr, 0, len); }

// ❌ Translating code to English
// Get the user from the database
let user = db.get_user(id)?;
```

### TODOs need a tracker reference

```rust
// ❌ Will rot forever
// TODO: handle reconnection

// ✅ Tracked
// TODO(BNLE-142): handle reconnection backoff
```

---

## Frameworks

When the project uses these frameworks, also load the corresponding reference:

| Framework | Reference |
|-----------|-----------|
| **tokio**, async runtimes | `rust-async-patterns.md` |
| **leptos** (web) | `rust-leptos-patterns.md` |
| **gpui** (desktop UI) | `rust-gpui-patterns.md` |

---

## Quick Reference Checklist

### Ownership
- [ ] `&str`/`&[T]` in arguments, not `&String`/`&Vec<T>`
- [ ] Owned types only when storing, returning transformed, or sending to thread
- [ ] No `.clone()` to silence the borrow checker
- [ ] `Copy` only on stack-only types ≤ 24 bytes
- [ ] `Arc<T>` for shared-immutable across threads, `Rc<T>` single-threaded

### Errors
- [ ] Public functions return `Result<T, ConcreteError>`
- [ ] No `unwrap()`/`expect()` outside tests/const
- [ ] `thiserror` for libraries, `anyhow` for binaries only
- [ ] `?` for propagation; `let ... else` for early exit
- [ ] Errors implement `Send + Sync + 'static` for async

### Types
- [ ] Newtypes for IDs, money, units (no naked `u64`/`String` for domain values)
- [ ] Enums for state machines (no parallel `bool` flags)
- [ ] `NonZeroU*`, `Path`, `&Path` for stdlib invariants
- [ ] Typestate for multi-step protocols / builders with required fields

### Iterators
- [ ] Chains over manual loops unless early exit needed
- [ ] No intermediate `.collect()` (clippy::needless_collect)
- [ ] `.sum()`/`.min()`/`.find()` over manual fold

### Async
- [ ] No `std::fs`/`std::net`/blocking calls in `async fn`
- [ ] `tokio::task::spawn_blocking` for CPU-bound work
- [ ] No sync `Mutex` held across `.await`
- [ ] Spawned tasks: `Send + 'static`

### Tooling
- [ ] `cargo clippy --all-targets --all-features --locked -- -D warnings` clean
- [ ] `cargo fmt` clean
- [ ] Workspace `[lints]` table configured
- [ ] `#[expect]` over `#[allow]` with `reason = "..."`

### Docs
- [ ] `///` on every `pub` item (libraries: `#![warn(missing_docs)]`)
- [ ] `# Errors` and `# Panics` sections where applicable
- [ ] `// SAFETY:` on every `unsafe` block
- [ ] TODOs reference a ticket

---

## Performance

> **Rust's ownership model is a performance feature.** Borrow by default, own when the type needs it, clone last.

### Parallel awaits, never `await` in a loop

```rust
// ❌ Serial I/O
let user = fetch_user(id).await?;
let orders = fetch_orders(id).await?;

// ✅ Parallel
let (user, orders) = tokio::try_join!(fetch_user(id), fetch_orders(id))?;

// ❌ Serialized loop over independent I/O
let mut results = vec![];
for id in ids { results.push(fetch_one(id).await?); }

// ✅ Bounded-concurrency stream
use futures::stream::{self, StreamExt};
let results: Vec<_> = stream::iter(ids)
    .map(|id| fetch_one(id))
    .buffer_unordered(16)
    .collect()
    .await;
```

### Never hold `std::sync::Mutex` across `.await`

```rust
// ❌ Deadlock-prone; also blocks the Tokio worker
let guard = state.lock().unwrap();
do_async_work().await;  // holding the lock this entire time

// ✅ Drop the guard before awaiting
let value = {
    let guard = state.lock().unwrap();
    guard.snapshot()
};  // guard dropped here
do_async_work(value).await;

// ✅ Or use tokio's Mutex if the lock must span an await
let guard = state.lock().await;
```

### Singleton clients (pooled connections are the point)

```rust
// ❌ New client per request — no pool, new TLS every call
let client = reqwest::Client::new();

// ✅ Shared client
static HTTP: OnceLock<reqwest::Client> = OnceLock::new();
fn http() -> &'static reqwest::Client {
    HTTP.get_or_init(|| reqwest::Client::builder().build().unwrap())
}
```

Same for `sqlx::PgPool` / `deadpool` / `bb8` — one pool per app, cloned cheaply (it's an `Arc` inside).

### Release profile with LTO + `codegen-units=1`

```toml
# Cargo.toml — deploy/release profile
[profile.release]
lto = "thin"
codegen-units = 1
strip = "symbols"
```

Typically 10–30% faster binaries at the cost of build time. Cheap to add; measure on your workload.

### `Bytes` / `BytesMut` for network buffers

`Vec<u8>` is fine for owned data. For buffers that get sliced, cloned, or passed across tasks, `bytes::Bytes` is reference-counted — cheap `Clone`, zero-copy slicing.

### Cheap wins on hashing / small collections

```rust
// ❌ SipHash (DoS-resistant but slow) on internal maps where the keys aren't adversarial
use std::collections::HashMap;

// ✅ Faster hasher for internal-only maps
use rustc_hash::FxHashMap;       // or ahash::AHashMap / foldhash
let mut m: FxHashMap<u64, Value> = FxHashMap::default();

// ✅ Stack-allocated for known-small collections
use smallvec::SmallVec;
let mut v: SmallVec<[u32; 8]> = SmallVec::new();  // no heap alloc until 9th element
```

(Keep `std::HashMap` for anything that takes external input — HashDoS is real.)

### Iterator chains, not intermediate `.collect()`s

```rust
// ❌ Two allocations
let active: Vec<_> = users.iter().filter(|u| u.active).collect();
let names: Vec<_> = active.iter().map(|u| &u.name).collect();

// ✅ Single pass, single allocation
let names: Vec<_> = users.iter().filter(|u| u.active).map(|u| &u.name).collect();
```

Clippy's `needless_collect` catches most of these.

### `Cow<'_, T>` when sometimes you own, sometimes you borrow

```rust
use std::borrow::Cow;

fn normalize(input: &str) -> Cow<'_, str> {
    if input.chars().all(|c| c.is_ascii_lowercase()) {
        Cow::Borrowed(input)           // already normalized — no alloc
    } else {
        Cow::Owned(input.to_lowercase())
    }
}
```

Beats "always allocate, always return `String`."

### Bound user-driven allocations

```rust
// ❌ DoS vector — user-controlled capacity
let mut v = Vec::with_capacity(user_input);

// ✅ Clamp
const MAX: usize = 10_000;
let cap = user_input.min(MAX);
let mut v = Vec::with_capacity(cap);
```

### Traps

- **`.await` inside a `for` loop.** Use `try_join!` / `FuturesUnordered` / `buffer_unordered(n)`.
- **Holding `std::sync::Mutex` across `.await`.** Deadlock + blocks the worker.
- **`.clone()` to dodge the borrow checker on hot paths.** Usually `Arc`, `&`, or `Cow` is what you want.
- **Unbounded `Vec::with_capacity(user_input)`.** Clamp.
- **`reqwest::Client::new()` per call.** Singleton.
- **Sync crypto / hashing (bcrypt, argon2) inside `async fn`.** Use `spawn_blocking`.
- **JSON hot paths with default `serde_json`.** `simd-json` / `sonic-rs` on measured hot paths only.

### Performance Checklist

- [ ] `tokio::try_join!` / `buffer_unordered` for parallel I/O; no `.await` in loops over independent work
- [ ] No `std::sync::Mutex` held across `.await`
- [ ] HTTP / DB clients as singletons (`OnceLock` / app state), not per call
- [ ] Release profile with `lto = "thin"`, `codegen-units = 1`, `strip`
- [ ] `Bytes` / `BytesMut` for network buffers; `Arc` for shared read; `Cow` for maybe-owned
- [ ] `FxHashMap` / `ahash` on internal maps (not external input)
- [ ] `SmallVec` / `ArrayVec` for known-small collections
- [ ] Iterator chains without intermediate `.collect()`s
- [ ] No user-unbounded `Vec::with_capacity` / recursion
- [ ] CPU-bound work in `spawn_blocking`, not on the Tokio worker
