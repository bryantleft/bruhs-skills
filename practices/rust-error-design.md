# Error Design

How to design error types in Rust crates and binaries. Loaded by `cook` and `slop` when working in Rust.

> Errors are values. They flow through `Result<T, E>` and propagate via `?`. Designing error types well costs little; doing it badly costs every caller.

## Contents

- [The Library/Binary Split](#the-librarybinary-split)
- [Crate-Level Error Enums (`thiserror`)](#crate-level-error-enums-thiserror)
- [Error Hierarchies](#error-hierarchies)
- [Single-Variant Errors: Struct, Not Enum](#single-variant-errors-struct-not-enum)
- [`#[from]` vs `#[source]`](#from-vs-source)
- [The `?` Operator](#the--operator)
- [Recovering vs Logging vs Transforming](#recovering-vs-logging-vs-transforming)
- [`unwrap` / `expect` Policy](#unwrap--expect-policy)
- [`panic!` vs `todo!` vs `unimplemented!` vs `unreachable!`](#panic-vs-todo-vs-unimplemented-vs-unreachable)
- [Async Error Bounds](#async-error-bounds)
- [Binary Error Handling (`anyhow`)](#binary-error-handling-anyhow)
- [Testing Errors](#testing-errors)
- [Quick Checklist](#quick-checklist)

---

## The Library/Binary Split

| | Library | Binary |
|---|---------|--------|
| **Goal** | Callers can match and handle each error variant | Operator sees a clear root cause |
| **Crate** | `thiserror` | `anyhow` (top level), `thiserror` (subsystems) |
| **Type** | Concrete enum or struct | `anyhow::Result<T>` |
| **Boxing** | Avoid `Box<dyn Error>` | Fine — `anyhow::Error` already boxes |

**Why never `anyhow` in a library:** `anyhow::Error` erases the variant. Callers can't write `match` arms or `if let` patterns. A library that returns `anyhow::Error` is a library you can't build robust software on top of.

---

## Crate-Level Error Enums (`thiserror`)

```rust
use thiserror::Error;

#[derive(Debug, Error)]
pub enum DbError {
    #[error("connection to {host}:{port} failed")]
    Connect { host: String, port: u16 },

    #[error("query timed out after {seconds}s")]
    QueryTimeout { seconds: u64 },

    #[error("no row found for id {0}")]
    NotFound(UserId),

    #[error("malformed row: {field}")]
    Schema { field: &'static str },

    // Wrap upstream errors transparently — callers see the inner Display
    #[error(transparent)]
    Sqlx(#[from] sqlx::Error),

    // Wrap with context message
    #[error("io while reading {path}: {source}")]
    Io {
        path: PathBuf,
        #[source]
        source: io::Error,
    },
}
```

### Error message style

- **Lowercase, no trailing period** — errors compose: `"db error: connection to localhost:5432 failed"`
- **Include the value, not just the type** — `"no row found for id 42"` beats `"row not found"`
- **No "Error" or "Failed" prefix** — context is added by callers

```rust
// ❌ Awkward when wrapped
#[error("Error: User not found")]
NotFound,
// → "db error: Error: User not found"

// ✅ Composes cleanly
#[error("user {0} not found")]
NotFound(UserId),
// → "db error: user 42 not found"
```

---

## Error Hierarchies

Each layer owns its error type. Layers above wrap with `#[from]`:

```rust
// db/error.rs
#[derive(Debug, Error)]
pub enum DbError { /* ... */ }

// http/error.rs
#[derive(Debug, Error)]
pub enum HttpError { /* ... */ }

// service/error.rs — composes lower layers
#[derive(Debug, Error)]
pub enum ServiceError {
    #[error("database: {0}")]
    Db(#[from] DbError),

    #[error("http: {0}")]
    Http(#[from] HttpError),

    #[error("validation: {0}")]
    Validation(String),
}
```

Now any `db::*` function called with `?` inside a service function automatically converts:

```rust
fn handle(req: &Request) -> Result<Response, ServiceError> {
    let user = db::find_user(req.id)?;       // DbError → ServiceError
    let body = http::render(&user)?;          // HttpError → ServiceError
    Ok(Response::ok(body))
}
```

---

## Single-Variant Errors: Struct, Not Enum

When a function or module has only one error condition, a struct is cleaner:

```rust
// ❌ Single-variant enum
#[derive(Debug, Error)]
pub enum ParseError {
    #[error("invalid input at byte {0}")]
    Invalid(usize),
}

// ✅ Struct
#[derive(Debug, Error)]
#[error("invalid input at byte {position}")]
pub struct ParseError {
    pub position: usize,
}
```

If you later need a second variant, refactor to an enum then.

---

## `#[from]` vs `#[source]`

```rust
#[derive(Debug, Error)]
pub enum MyError {
    // #[from] — auto-conversion via ? from io::Error to MyError::Io
    #[error("io error: {0}")]
    Io(#[from] io::Error),

    // #[source] — preserves error chain but no auto-conversion (need .map_err)
    #[error("config invalid")]
    Config {
        #[source]
        cause: serde_json::Error,
    },

    // #[error(transparent)] — defers Display + source to inner error
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}
```

Use `#[from]` when the conversion is unambiguous (one variant per source type). If two variants both wrap `io::Error`, you can't use `#[from]` on both — pick the more specific one and use `#[source]` on the other with explicit `.map_err`.

---

## The `?` Operator

```rust
// ✅ Flat
fn handle(req: &Request) -> Result<Response, Error> {
    let validated = validate(req)?;
    let user = lookup(validated.id)?;
    let body = render(&user)?;
    Ok(Response::ok(body))
}

// ❌ Match chain — verbose, nested
fn handle(req: &Request) -> Result<Response, Error> {
    match validate(req) {
        Ok(validated) => match lookup(validated.id) {
            Ok(user) => match render(&user) {
                Ok(body) => Ok(Response::ok(body)),
                Err(e) => Err(e.into()),
            },
            Err(e) => Err(e.into()),
        },
        Err(e) => Err(e.into()),
    }
}
```

### When `?` is wrong

```rust
// ❌ Discards info you need
fn try_each(items: &[Item]) -> Result<Vec<Output>, Error> {
    items.iter().map(process).collect()  // ? would short-circuit on first error
}

// ✅ Collect failures explicitly
fn try_each(items: &[Item]) -> (Vec<Output>, Vec<Error>) {
    let mut ok = Vec::new();
    let mut err = Vec::new();
    for item in items {
        match process(item) {
            Ok(o) => ok.push(o),
            Err(e) => err.push(e),
        }
    }
    (ok, err)
}
```

---

## Recovering vs Logging vs Transforming

### `inspect_err` for logging without consuming

```rust
let result = parse(input)
    .inspect_err(|e| tracing::error!(error = %e, "parse failed"))?;
```

### `map_err` to transform error type

```rust
let port: u16 = config.port_str
    .parse()
    .map_err(|_| ConfigError::InvalidPort(config.port_str.clone()))?;
```

### `or_else` to recover

```rust
let cached = fetch_remote(id)
    .or_else(|_| fetch_local_cache(id))?;
```

### `let ... else` for early exit on `Option`

```rust
let Some(user) = find_user(id) else {
    return Err(ServiceError::UserNotFound(id));
};
```

---

## `unwrap` / `expect` Policy

**Allowed:**
- Tests (`#[test]`, `#[cfg(test)]` modules, integration tests)
- Examples and benches
- `const` / `static` initialization where failure should be a build/startup error
- After explicit invariant proof: `let Some(x) = opt else { unreachable!("checked above") }`

**Banned in production code paths.** Use clippy to enforce:

```toml
[workspace.lints.clippy]
unwrap_used = "deny"
expect_used = "warn"  # warn — sometimes legitimate with descriptive message
```

If you `expect()`, the message must explain the **invariant**, not the error:

```rust
// ❌ Useless on panic
config.port.expect("port should be set")

// ✅ Explains why this can't fail
LOCK.try_lock().expect("LOCK is only acquired by main thread, which holds it for life")
```

---

## `panic!` vs `todo!` vs `unimplemented!` vs `unreachable!`

| Macro | Use | Strips in release? |
|-------|-----|--------------------|
| `panic!("msg")` | Bug — invariant violated | No |
| `unreachable!()` | Code path the compiler can't prove is dead | No |
| `todo!()` | Stub — fail loudly until implemented | No |
| `unimplemented!()` | Trait method intentionally unsupported | No |
| `debug_assert!(...)` | Cheap debug-only invariant check | Yes |

```rust
// ✅ Honest about being a stub — won't slip into prod
fn process_v2(item: &Item) -> Result<Output, Error> {
    todo!("BNLE-142: implement v2 processing")
}

// ✅ Compiler doesn't know an enum is exhausted by guards
match status {
    Status::Active => act(),
    Status::Closed => close(),
    other if other.is_terminal() => terminate(),
    _ => unreachable!("all terminal statuses handled by guard above"),
}
```

---

## Async Error Bounds

Async errors need `Send + Sync + 'static` to cross `.await` boundaries cleanly and to be storable in `JoinHandle<Result<T, E>>`.

```rust
// ✅ thiserror-derived enums implement Send + Sync if all variants do
#[derive(Debug, Error)]
pub enum FetchError {
    #[error(transparent)]
    Http(#[from] reqwest::Error),  // reqwest::Error: Send + Sync ✓
    #[error("timeout after {0:?}")]
    Timeout(Duration),
}

async fn worker() -> Result<(), FetchError> {
    let data = fetch().await?;
    process(data).await
}

// JoinHandle<Result<(), FetchError>> works
let handle: JoinHandle<Result<(), FetchError>> = tokio::spawn(worker());
```

If your error wraps `dyn Error`, force the bounds:

```rust
#[derive(Debug, Error)]
#[error("dynamic: {0}")]
pub struct DynError(pub Box<dyn std::error::Error + Send + Sync + 'static>);
```

---

## Binary Error Handling (`anyhow`)

```rust
use anyhow::{Context, Result, bail};

fn main() -> Result<()> {
    let config = load_config()
        .context("loading config from $HOME/.bruhsrc")?;

    if config.api_key.is_empty() {
        bail!("api_key is required in config");
    }

    run(&config).context("running main loop")?;
    Ok(())
}
```

`anyhow::Error` Display walks the chain:
```
running main loop

Caused by:
    0: connecting to api.example.com
    1: dns lookup failed
    2: temporary failure in name resolution
```

### Use `.context()` heavily

```rust
// ✅ Each layer adds context — operators can read the chain
fn process_file(path: &Path) -> Result<()> {
    let bytes = fs::read(path)
        .with_context(|| format!("reading {}", path.display()))?;
    let parsed: Config = serde_json::from_slice(&bytes)
        .with_context(|| format!("parsing config from {}", path.display()))?;
    apply(&parsed).context("applying config")?;
    Ok(())
}
```

---

## Testing Errors

```rust
// ✅ Match on variants when error type is your own enum
#[test]
fn missing_field_returns_validation_error() {
    let err = parse_config("").unwrap_err();
    assert!(matches!(err, ConfigError::MissingField { name: "host", .. }));
}

// ✅ String-match Display when error type is opaque (anyhow, dyn Error)
#[test]
fn timeout_message_includes_duration() {
    let err = call_with_timeout().unwrap_err();
    assert!(err.to_string().contains("timeout after 5s"));
}
```

For snapshot-style assertions, `insta` is excellent for error messages:

```rust
#[test]
fn invalid_input_error() {
    insta::assert_snapshot!(parse("???").unwrap_err());
}
```

---

## Quick Checklist

- [ ] Libraries: concrete `thiserror` enum, never `anyhow::Result`
- [ ] Binaries: `anyhow::Result` at edges, `thiserror` for subsystems
- [ ] Lowercase error messages, include the value
- [ ] `#[from]` for one-to-one wrapping; `#[source]` otherwise
- [ ] No `unwrap()`/`expect()` outside tests/const (clippy enforced)
- [ ] `expect()` message explains the invariant, not the error
- [ ] `?` for propagation; `let ... else` for early exit
- [ ] Async error types: `Send + Sync + 'static`
- [ ] `inspect_err` for logging without consuming
- [ ] `.context()` liberally in binaries; chain reads top-down
