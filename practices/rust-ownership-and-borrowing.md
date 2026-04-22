# Ownership & Borrowing

Deep reference for ownership decisions in Rust. Loaded by `cook` and `slop` when working in Rust crates.

> Every value has exactly one owner. Borrows are temporary read or write loans. The borrow checker is your design partner — fight it once, learn the lesson, never fight it again.

## Contents

- [Function Signatures: The First Decision](#function-signatures-the-first-decision)
- [Clone: When and Why](#clone-when-and-why)
- [Cow — Clone on Write](#cow--clone-on-write)
- [Copy: The 24-Byte Rule](#copy-the-24-byte-rule)
- [Rc vs Arc vs Box](#rc-vs-arc-vs-box)
- [Lifetimes: Keep Them Implicit](#lifetimes-keep-them-implicit)
- [RAII: Drop Guards](#raii-drop-guards)
- [Interior Mutability: Choose Carefully](#interior-mutability-choose-carefully)
- [Quick Checklist](#quick-checklist)

---

## Function Signatures: The First Decision

### The Ownership Decision Matrix

| You will... | Take |
|-------------|------|
| Read only, briefly | `&T` |
| Read a string | `&str` |
| Read a slice of any kind | `&[T]` |
| Read a path | `&Path` |
| Mutate in place, briefly | `&mut T` |
| Store the value, send to thread, transform-and-return owned | `T` |
| Sometimes need to mutate, sometimes not | `Cow<'_, T>` |
| Caller might pass owned or borrowed | `impl Into<String>` / `AsRef<Path>` |

### The classic mistakes

```rust
// ❌ Forces every caller to allocate
fn validate(name: String) -> bool { /* ... */ }

// ❌ Pointless indirection — &String / &Vec<T> are almost never right
fn validate(name: &String) -> bool { /* ... */ }
fn sum(values: &Vec<u32>) -> u32 { /* ... */ }

// ✅ Borrow the slice
fn validate(name: &str) -> bool { /* ... */ }
fn sum(values: &[u32]) -> u32 { /* ... */ }
```

### Generic acceptance with `AsRef`

```rust
// ✅ Accepts &str, String, PathBuf, &Path, etc.
fn open<P: AsRef<Path>>(path: P) -> io::Result<File> {
    File::open(path.as_ref())
}

open("config.toml")?;
open(String::from("config.toml"))?;
open(PathBuf::from("/etc/config"))?;
```

---

## Clone: When and Why

### Legitimate `.clone()` use cases

```rust
// ✅ Need ownership, caller still needs it too
fn store(name: &str, store: &mut Vec<String>) {
    store.push(name.to_string());  // .to_string() == .clone() for &str
}

// ✅ Spawning a task — task needs 'static
let user = current_user.clone();
tokio::spawn(async move {
    log_event(user).await;
});

// ✅ Cheap clones (Arc, Rc, Copy types) — these aren't deep clones
let shared = Arc::clone(&state);
```

### Anti-patterns

```rust
// ❌ Clone to silence borrow checker
fn process(items: &[Item]) -> Vec<Item> {
    items.to_vec()  // why? do you actually need owned items?
}

// ❌ Clone in iterator chain
let names: Vec<String> = users.iter().map(|u| u.name.clone()).collect();
// ✅ If you need owned, use .cloned() — explicit at the call site
let names: Vec<String> = users.iter().map(|u| &u.name).cloned().collect();
// ✅ Better — borrow if you can
let names: Vec<&str> = users.iter().map(|u| u.name.as_str()).collect();

// ❌ Cloning then taking a reference
let cloned = data.clone();
helper(&cloned);
// ✅ Just borrow
helper(data);
```

### The `Arc::clone` convention

```rust
// ❌ Ambiguous — looks like a deep clone of T
let state2 = state.clone();

// ✅ Explicit — clearly an Arc bump, not a T clone
let state2 = Arc::clone(&state);
```

---

## Cow — Clone on Write

Use `Cow<'_, T>` when a function might return either borrowed or owned data, depending on input.

```rust
use std::borrow::Cow;

// Returns the input unchanged if no escaping needed (no allocation)
// Returns an owned escaped copy otherwise
fn html_escape(input: &str) -> Cow<'_, str> {
    if input.contains(['<', '>', '&']) {
        Cow::Owned(input.replace('<', "&lt;").replace('>', "&gt;").replace('&', "&amp;"))
    } else {
        Cow::Borrowed(input)
    }
}

// Caller pays nothing for the common case
let safe = html_escape("hello world");          // Borrowed
let safe = html_escape("<script>alert(1)</script>");  // Owned
```

---

## Copy: The 24-Byte Rule

A type can derive `Copy` if:
1. **All fields implement `Copy`**
2. **Total size ≤ 24 bytes** (3 words on 64-bit) — heuristic, not a rule
3. **No heap allocation** (no `String`, `Vec`, `Box`, `Rc`, `Arc`)
4. **Semantic copy makes sense** (copying represents the same value, not shared identity)

### Primitive sizes (64-bit)

| Type | Bytes |
|------|-------|
| `bool`, `u8`, `i8` | 1 |
| `u16`, `i16` | 2 |
| `u32`, `i32`, `f32`, `char` | 4 |
| `u64`, `i64`, `f64`, `usize`, `isize` | 8 |
| `u128`, `i128` | 16 |
| `&T`, `&mut T` (thin) | 8 |
| `&[T]`, `&str` (fat) | 16 |

### Good Copy candidates

```rust
#[derive(Debug, Copy, Clone, PartialEq)]
struct Rgba(u8, u8, u8, u8);  // 4 bytes

#[derive(Debug, Copy, Clone)]
struct Point { x: f32, y: f32 }  // 8 bytes

#[derive(Debug, Copy, Clone)]
enum Direction { N, S, E, W }  // 1 byte (no payload)
```

### Bad Copy candidates

```rust
// ❌ Has heap allocation
#[derive(Clone)]
struct User { id: u64, name: String }

// ❌ Too large — cheap to move, expensive to copy
#[derive(Clone)]
struct Matrix4x4([f64; 16]);  // 128 bytes

// ❌ Identity matters — Copy would silently duplicate the handle
struct FileHandle(RawFd);
```

---

## Rc vs Arc vs Box

| Type | Threads | Mutability | Use when |
|------|---------|------------|----------|
| `Box<T>` | Either | Owned-mutable | Heap allocation, single owner, trait objects |
| `Rc<T>` | Single | Shared-immutable | Shared ownership in single-threaded code |
| `Arc<T>` | Multi | Shared-immutable | Shared ownership across threads |
| `Rc<RefCell<T>>` | Single | Shared-mutable | Interior mutability, single-threaded |
| `Arc<Mutex<T>>` | Multi | Shared-mutable | Shared mutable state across threads |
| `Arc<RwLock<T>>` | Multi | Many readers, one writer | Read-heavy shared state |

### Rule of thumb

- **Default to `Box<T>`** — single owner, heap allocation, minimal overhead.
- **Reach for `Arc<T>`** when you genuinely need to share. Don't reach for `Rc<T>` first then refactor — most code grows into multithreaded eventually.
- **`Mutex` over `RwLock`** unless you've measured contention — `RwLock` is heavier per acquisition.

---

## Lifetimes: Keep Them Implicit

Most lifetimes can be elided. Only annotate when the compiler can't infer.

```rust
// ✅ Elided — compiler infers
fn first(xs: &[u32]) -> Option<&u32> { xs.first() }

// ❌ Unnecessary explicit lifetimes — noise
fn first<'a>(xs: &'a [u32]) -> Option<&'a u32> { xs.first() }

// ✅ Explicit when relating multiple input lifetimes
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}

// ✅ Explicit when struct holds a reference
struct Parser<'src> {
    input: &'src str,
    pos: usize,
}
```

### Avoid `'static` when borrowing works

```rust
// ❌ Forces caller to leak or use Box::leak
fn config_path() -> &'static str { /* ... */ }

// ✅ Returns owned
fn config_path() -> String { /* ... */ }
// or borrowed from self
impl Config { fn path(&self) -> &str { &self.path } }
```

### Variance gotcha — `PhantomData`

```rust
// PhantomData<T>           — covariant in T (default)
// PhantomData<&'a T>       — covariant in 'a and T
// PhantomData<&'a mut T>   — covariant in 'a, invariant in T
// PhantomData<fn(T)>       — contravariant in T
// PhantomData<*const T>    — invariant; doesn't impose Send/Sync
```

Most newtype wrappers should use `PhantomData<fn() -> T>` to opt out of `Send`/`Sync` propagation while remaining variance-flexible.

---

## RAII: Drop Guards

Resource cleanup belongs in `Drop`, not in `defer`-style code at the end of a function. The borrow checker guarantees `Drop` runs.

```rust
// ✅ Cleanup happens whether function returns Ok, Err, or panics
struct TempFile(PathBuf);

impl Drop for TempFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

fn process() -> Result<(), Error> {
    let _temp = TempFile(PathBuf::from("/tmp/work.bin"));
    do_stuff()?;  // even if this returns Err, file is removed
    Ok(())
}
```

### Idiomatic guard pattern

```rust
// Span guard for tracing
struct SpanGuard { _entered: tracing::span::EnteredSpan }

fn enter_span(name: &'static str) -> SpanGuard {
    let span = tracing::info_span!(name);
    SpanGuard { _entered: span.entered() }
}

fn work() {
    let _guard = enter_span("work");
    // ... span is active until _guard drops at end of scope
}
```

---

## Interior Mutability: Choose Carefully

| Type | Single-thread | Multi-thread | Notes |
|------|---------------|--------------|-------|
| `Cell<T>` | ✅ | ❌ | `T: Copy`, value-based |
| `RefCell<T>` | ✅ | ❌ | Runtime-borrow-checked |
| `Mutex<T>` | ✅ | ✅ | Locks; can poison on panic |
| `RwLock<T>` | ✅ | ✅ | Reader/writer; can poison |
| `OnceCell<T>` / `OnceLock<T>` | ✅ | ✅ | Init-once; `OnceLock` is multi-thread |
| `AtomicU*` etc. | ✅ | ✅ | Lock-free, integer-typed |

```rust
// ✅ OnceLock for lazy global
use std::sync::OnceLock;

fn config() -> &'static Config {
    static CONFIG: OnceLock<Config> = OnceLock::new();
    CONFIG.get_or_init(|| Config::load())
}
```

---

## Quick Checklist

- [ ] Function args take `&str`, `&[T]`, `&Path`, `&T` by default
- [ ] `String`/`Vec<T>` only when storing or transforming and returning owned
- [ ] No `&String` or `&Vec<T>` — use slices
- [ ] `Cow<'_, T>` when ownership depends on the input
- [ ] `Copy` only on small (≤ 24-byte) heap-free types
- [ ] `Arc::clone(&x)` not `x.clone()` for clarity
- [ ] No `.clone()` to silence the borrow checker
- [ ] Lifetimes elided unless required
- [ ] `Drop` for resource cleanup, not manual `cleanup()` calls
- [ ] `OnceLock` for lazy globals
