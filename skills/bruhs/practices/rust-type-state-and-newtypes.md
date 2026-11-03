# Type State & Newtypes

Encoding domain rules in the type system. Loaded by `cook` and `slop` when working in Rust.

> The compiler is free labor. If a state can't be represented, it can't be reached. If a wrong argument can't be constructed, it can't be passed.

## Contents

- [Newtypes](#newtypes)
- [Stdlib Invariant Types](#stdlib-invariant-types)
- [Typestate Pattern](#typestate-pattern)
- [Sealed Traits](#sealed-traits)
- [Marker Traits](#marker-traits)
- [`From` / `Into` / `TryFrom` / `TryInto`](#from--into--tryfrom--tryinto)
- [`Default` and Builders](#default-and-builders)
- [Quick Checklist](#quick-checklist)

---

## Newtypes

A newtype wraps an existing type to give it a distinct identity.

### When to newtype

- **Domain identifiers** — `UserId`, `OrderId`, `SessionToken` (don't pass naked `u64` or `String`)
- **Units** — `Cents`, `Bytes`, `Milliseconds` (don't pass naked `u64`)
- **Validated values** — `Email`, `NonEmptyString`, `SortedVec<T>`
- **Wrappers around third-party types** to add or restrict trait implementations

### The base pattern

```rust
#[derive(Debug, Copy, Clone, PartialEq, Eq, Hash)]
pub struct UserId(u64);

impl UserId {
    pub fn new(id: u64) -> Self { Self(id) }
    pub fn get(self) -> u64 { self.0 }
}

impl fmt::Display for UserId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "user:{}", self.0)
    }
}
```

### Validated newtypes

Construction is the only place validation runs. Once constructed, the invariant holds forever.

```rust
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Email(String);

impl Email {
    pub fn parse(input: &str) -> Result<Self, EmailError> {
        if !input.contains('@') {
            return Err(EmailError::MissingAt);
        }
        Ok(Self(input.to_lowercase()))
    }

    pub fn as_str(&self) -> &str { &self.0 }
}

// ❌ No public constructor — can only get Email through `parse`
// Email("not-an-email".to_string())  // doesn't compile
```

### `#[repr(transparent)]` for zero-cost wrappers

```rust
// Same memory layout as u64 — safe to transmute to/from
#[repr(transparent)]
pub struct UserId(u64);

// Useful when interfacing with C or doing low-level work
extern "C" fn ffi(id: UserId) { /* ABI is identical to extern "C" fn ffi(id: u64) */ }
```

### Newtype + `Deref` — usually wrong

```rust
// ❌ Tempting but leaks the inner type — caller can call any String method
impl Deref for Email {
    type Target = String;
    fn deref(&self) -> &Self::Target { &self.0 }
}

// ✅ Expose only the methods you want
impl Email {
    pub fn as_str(&self) -> &str { &self.0 }
    pub fn domain(&self) -> &str { self.0.split('@').nth(1).unwrap_or("") }
}
```

`Deref` for newtypes breaks encapsulation. Reserve `Deref` for smart pointers (`Box`, `Rc`, `Arc`, `MutexGuard`).

---

## Stdlib Invariant Types

Use these instead of rolling your own where possible:

| Type | Invariant | Use for |
|------|-----------|---------|
| `NonZeroU8`/`U16`/`U32`/`U64`/`Usize` | Not zero | Page sizes, counts, positive offsets |
| `NonZeroI*` | Not zero | Same, signed |
| `Path` / `PathBuf` | Filesystem path | Always over `&str`/`String` for paths |
| `OsStr` / `OsString` | Platform-native string | Filenames, env vars |
| `Duration` | Non-negative time span | Timeouts, intervals |
| `Instant` | Monotonic time point | Elapsed measurements |

```rust
use std::num::NonZeroUsize;

// ✅ Compiler enforces > 0
fn chunks<T>(items: &[T], chunk_size: NonZeroUsize) -> Chunks<'_, T> {
    items.chunks(chunk_size.get())
}

// Caller must construct safely
let size = NonZeroUsize::new(10).expect("10 > 0");
chunks(&data, size);
```

---

## Typestate Pattern

Encode state in the type. Methods are only available on the right state. Illegal transitions are compile errors.

### When to use typestate

- **Multi-step protocols** — connect → authenticate → use → close
- **Builders with required fields** — must set name and age before `.build()`
- **Resource lifecycles** — opened/closed, locked/unlocked, drained/active
- **Streaming parsers** — header → body → trailer

### The Connection example

```rust
use std::marker::PhantomData;

pub struct Disconnected;
pub struct Connected;

pub struct Connection<S> {
    socket: Option<TcpStream>,
    _state: PhantomData<S>,
}

impl Connection<Disconnected> {
    pub fn new() -> Self {
        Self { socket: None, _state: PhantomData }
    }

    pub fn connect(self, addr: &str) -> io::Result<Connection<Connected>> {
        let socket = TcpStream::connect(addr)?;
        Ok(Connection {
            socket: Some(socket),
            _state: PhantomData,
        })
    }
}

impl Connection<Connected> {
    pub fn send(&mut self, data: &[u8]) -> io::Result<()> {
        let socket = self.socket.as_mut().expect("connected => socket is Some");
        socket.write_all(data)
    }

    pub fn close(self) -> Connection<Disconnected> {
        // socket dropped here
        Connection { socket: None, _state: PhantomData }
    }
}

// Usage:
let conn = Connection::new().connect("api.example.com:443")?;
conn.send(b"GET / HTTP/1.1\r\n\r\n")?;
//   ❌ conn.connect(...)  — doesn't exist on Connection<Connected>
let conn = conn.close();
//   ❌ conn.send(...)  — doesn't exist on Connection<Disconnected>
```

### `PhantomData` zero-cost

`PhantomData<T>` has size 0 — it disappears at compile time. The state is purely a type-level marker.

### Typestate Builder

For builders where some fields are required:

```rust
pub struct Unset;
pub struct Set;

pub struct ClientBuilder<HasUrl, HasToken> {
    url: Option<String>,
    token: Option<String>,
    timeout: Duration,
    _url: PhantomData<HasUrl>,
    _token: PhantomData<HasToken>,
}

impl ClientBuilder<Unset, Unset> {
    pub fn new() -> Self {
        Self {
            url: None,
            token: None,
            timeout: Duration::from_secs(30),
            _url: PhantomData,
            _token: PhantomData,
        }
    }
}

impl<H> ClientBuilder<Unset, H> {
    pub fn url(self, url: impl Into<String>) -> ClientBuilder<Set, H> {
        ClientBuilder {
            url: Some(url.into()),
            token: self.token,
            timeout: self.timeout,
            _url: PhantomData,
            _token: PhantomData,
        }
    }
}

impl<U> ClientBuilder<U, Unset> {
    pub fn token(self, token: impl Into<String>) -> ClientBuilder<U, Set> {
        ClientBuilder {
            url: self.url,
            token: Some(token.into()),
            timeout: self.timeout,
            _url: PhantomData,
            _token: PhantomData,
        }
    }
}

// Optional fields available on any state
impl<U, T> ClientBuilder<U, T> {
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }
}

// Build only when both required fields are Set
impl ClientBuilder<Set, Set> {
    pub fn build(self) -> Client {
        Client {
            url: self.url.expect("Set => Some"),
            token: self.token.expect("Set => Some"),
            timeout: self.timeout,
        }
    }
}

// Usage:
let client = ClientBuilder::new()
    .url("https://api.example.com")
    .token("secret")
    .timeout(Duration::from_secs(10))
    .build();

// ❌ Compile errors:
ClientBuilder::new().build();                 // missing url and token
ClientBuilder::new().url("...").build();      // missing token
ClientBuilder::new().token("...").build();    // missing url
```

### When NOT to use typestate

- **Trivial 2-state cases** — an enum is simpler
- **Runtime-determined transitions** — type-level state can't model `if cond { .a() } else { .b() }`
- **Heterogeneous collections** — `Vec<Connection<???>>` doesn't work; you'd need `Vec<Box<dyn ConnectionTrait>>`
- **Library APIs that need backwards compatibility** — adding a new state breaks every consumer

---

## Sealed Traits

Prevent downstream crates from implementing a trait, even if it's `pub`:

```rust
mod sealed {
    pub trait Sealed {}
}

pub trait MyTrait: sealed::Sealed {
    fn do_thing(&self);
}

// Only types in this crate can implement
impl sealed::Sealed for MyType {}
impl MyTrait for MyType {
    fn do_thing(&self) { /* ... */ }
}
```

Used by `std` for traits like `Pattern`, `SliceIndex`. Use when:
- You want to add methods to the trait later without breaking callers
- The trait has invariants downstream impls couldn't uphold

---

## Marker Traits

Empty traits as type-level tags.

```rust
pub trait Validated {}
pub trait Unvalidated {}

pub struct Request<S> {
    pub body: Vec<u8>,
    _marker: PhantomData<S>,
}

impl Request<Unvalidated> {
    pub fn validate(self, schema: &Schema) -> Result<Request<Validated>, ValidationError> {
        schema.validate(&self.body)?;
        Ok(Request { body: self.body, _marker: PhantomData })
    }
}

// Handler can require validated requests at the type level
fn handle(req: Request<Validated>) -> Response { /* ... */ }
```

### Custom `Send`/`Sync` opt-out

`PhantomData<*const T>` makes a type `!Send` and `!Sync` (raw pointers don't implement either). Useful for types that hold thread-local state:

```rust
pub struct ThreadLocalThing {
    inner: *mut SomeFfiHandle,
    _not_send: PhantomData<*const ()>,
}
```

---

## `From` / `Into` / `TryFrom` / `TryInto`

Conversions you implement:

| Trait | Direction | Failable | Use |
|-------|-----------|----------|-----|
| `From<T> for U` | `T → U` | No | Lossless conversion |
| `TryFrom<T> for U` | `T → U` | Yes | Validated conversion |
| `Into<U> for T` | `T → U` | No | Auto-derived from `From` |
| `TryInto<U> for T` | `T → U` | Yes | Auto-derived from `TryFrom` |

```rust
// ✅ Implement From; Into is free
impl From<u64> for UserId {
    fn from(id: u64) -> Self { Self(id) }
}

// ✅ TryFrom for validation
impl TryFrom<&str> for Email {
    type Error = EmailError;
    fn try_from(s: &str) -> Result<Self, Self::Error> {
        Self::parse(s)
    }
}

// Now both work:
let id: UserId = 42.into();
let email: Email = "user@example.com".try_into()?;
```

### `impl Trait` arguments for ergonomic APIs

```rust
// ✅ Accepts &str, String, &String, etc.
fn greet(name: impl Into<String>) {
    let name: String = name.into();
    println!("Hello, {name}");
}

greet("alice");
greet(String::from("bob"));
```

---

## `Default` and Builders

```rust
#[derive(Debug, Default)]
pub struct Config {
    pub port: u16,        // defaults to 0
    pub host: String,     // defaults to ""
    pub debug: bool,      // defaults to false
}

// Customize defaults via manual impl
impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            port: 8080,
            host: "0.0.0.0".to_string(),
            workers: NonZeroUsize::new(num_cpus::get()).expect("cpu count > 0"),
        }
    }
}

// Update syntax for partial customization
let config = ServerConfig {
    port: 9000,
    ..ServerConfig::default()
};
```

---

## Quick Checklist

- [ ] Domain IDs and units are newtypes, never naked `u64` / `String`
- [ ] Validated values have private fields and a `parse` / `try_from` constructor
- [ ] No `Deref` on newtypes — expose explicit accessor methods
- [ ] `NonZeroU*`, `Path`, `Duration` from stdlib over hand-rolled
- [ ] Typestate for multi-step protocols and builders with required fields
- [ ] `PhantomData` to encode state without runtime cost
- [ ] Sealed traits when invariants matter
- [ ] `From` for infallible conversion, `TryFrom` for validated
- [ ] `impl Into<T>` arguments for ergonomic public APIs
- [ ] `#[repr(transparent)]` when ABI-compatible newtype is required
