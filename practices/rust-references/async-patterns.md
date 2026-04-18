# Async Patterns

Tokio-based async Rust patterns. Loaded by `cook` and `slop` when `tokio`, `async-std`, or `axum` appears in `Cargo.toml`.

> Async functions are colored. Spawned tasks need `Send + 'static`. The runtime can't tell sync code from async — *you* have to keep blocking calls out of `async fn`.

---

## The Bounds That Bite

| Constraint | Where | Why |
|------------|-------|-----|
| `Send` | Spawned futures, types crossing `.await` on multi-thread runtime | Future may be moved between worker threads |
| `Sync` | Anything shared via `&` across threads | Multiple threads may read concurrently |
| `'static` | `tokio::spawn`, `JoinSet::spawn` | Task may outlive the spawning function |

```rust
// ❌ Won't compile — `Rc<T>` is not Send
let cache = Rc::new(Cache::new());
tokio::spawn(async move {
    use_cache(&cache).await;  // ERROR: Rc cannot be sent between threads
});

// ✅ Use Arc instead
let cache = Arc::new(Cache::new());
let cache_clone = Arc::clone(&cache);
tokio::spawn(async move {
    use_cache(&cache_clone).await;
});
```

---

## Never Block in `async fn`

The cardinal sin. A blocked worker thread can't make progress on any other task.

```rust
// ❌ Blocking call in async — starves the runtime
async fn read_config() -> io::Result<String> {
    std::fs::read_to_string("config.toml")  // SYNC I/O
}

// ❌ Blocking sleep
async fn wait() {
    std::thread::sleep(Duration::from_secs(1));  // BLOCKS WORKER
}

// ❌ Synchronous channel recv
async fn consume(rx: std::sync::mpsc::Receiver<Msg>) {
    let msg = rx.recv().unwrap();  // BLOCKS
}
```

```rust
// ✅ Async I/O
async fn read_config() -> io::Result<String> {
    tokio::fs::read_to_string("config.toml").await
}

// ✅ Async sleep — yields to runtime
async fn wait() {
    tokio::time::sleep(Duration::from_secs(1)).await;
}

// ✅ Async channel
async fn consume(mut rx: tokio::sync::mpsc::Receiver<Msg>) {
    while let Some(msg) = rx.recv().await { /* ... */ }
}
```

### CPU-bound work: `spawn_blocking`

```rust
async fn hash_password(password: String) -> [u8; 32] {
    tokio::task::spawn_blocking(move || {
        // bcrypt, argon2, etc. — pure CPU
        argon2_hash(&password)
    })
    .await
    .expect("hash task panicked")
}
```

`spawn_blocking` runs on a dedicated thread pool. Use it for:
- Cryptography (hashing, signing)
- Heavy serialization
- Calls into sync C libraries
- Anything that takes more than ~10ms of CPU

---

## Locks Across `.await`

```rust
// ❌ Holds std::sync::Mutex across .await — deadlock risk + non-Send future
async fn bad(state: Arc<std::sync::Mutex<State>>) {
    let guard = state.lock().unwrap();
    fetch_remote(&guard.url).await;  // .await with sync lock held
}

// ✅ Drop the lock before awaiting
async fn good(state: Arc<std::sync::Mutex<State>>) {
    let url = {
        let guard = state.lock().unwrap();
        guard.url.clone()
    };  // guard dropped here
    fetch_remote(&url).await;
}

// ✅ Use tokio::sync::Mutex when you must hold across .await
async fn also_good(state: Arc<tokio::sync::Mutex<State>>) {
    let guard = state.lock().await;
    fetch_remote(&guard.url).await;  // OK — async-aware lock
}
```

**Default to `std::sync::Mutex`** for short critical sections. Only reach for `tokio::sync::Mutex` when you genuinely need to hold the lock across an `.await`.

---

## Spawning: `spawn`, `JoinSet`, `JoinHandle`

### One-shot task

```rust
let handle = tokio::spawn(async move {
    let data = fetch().await?;
    process(data).await
});

let result: Result<Output, Error> = handle.await.expect("task panicked");
```

### Many tasks with results — `JoinSet`

```rust
use tokio::task::JoinSet;

let mut set = JoinSet::new();
for url in urls {
    set.spawn(async move { fetch(&url).await });
}

let mut results = Vec::new();
while let Some(joined) = set.join_next().await {
    let result = joined.expect("task panicked");
    results.push(result);
}
```

### Bounded concurrency — semaphore

```rust
use tokio::sync::Semaphore;

let sem = Arc::new(Semaphore::new(10));  // max 10 concurrent

let mut set = JoinSet::new();
for url in urls {
    let permit = Arc::clone(&sem).acquire_owned().await.unwrap();
    set.spawn(async move {
        let _permit = permit;  // released on drop
        fetch(&url).await
    });
}
```

### Wait for all — `try_join_all`

```rust
use futures::future::try_join_all;

let results: Vec<Output> = try_join_all(
    items.iter().map(|item| process(item))
).await?;
```

`try_join_all` runs futures **concurrently in the same task** (no spawning). Use it when:
- Tasks share borrowed data (no `'static` needed)
- You want first-error short-circuit
- Concurrency level is bounded by the iterator size

---

## Cancellation

Tokio futures are cancelled by **dropping** them. Make sure your code is cancel-safe.

### Cancel-safe operations

```rust
// ✅ Safe to drop — leaves no half-state
tokio::time::sleep(d).await;
tokio::sync::Notify::notified().await;
tokio::sync::oneshot::Receiver::recv().await;
tokio::sync::mpsc::Receiver::recv().await;
```

### NOT cancel-safe

```rust
// ❌ tokio::io::AsyncReadExt::read may consume bytes then drop them on cancel
reader.read(&mut buf).await?;
```

Read the docs of every async method you use inside `select!`. The Tokio docs explicitly mark which are cancel-safe.

### `select!` for racing

```rust
use tokio::select;

select! {
    msg = rx.recv() => handle(msg),
    _ = tokio::time::sleep(Duration::from_secs(5)) => timeout(),
    _ = shutdown.notified() => return,
}
```

### Graceful shutdown — `CancellationToken`

```rust
use tokio_util::sync::CancellationToken;

let token = CancellationToken::new();
let child = token.child_token();

tokio::spawn(async move {
    select! {
        _ = work() => {},
        _ = child.cancelled() => cleanup(),
    }
});

// Later — signal shutdown
token.cancel();
```

---

## Channels: Picking the Right One

| Channel | Multi-producer | Multi-consumer | Bounded | Use |
|---------|----------------|----------------|---------|-----|
| `tokio::sync::mpsc` | ✅ | ❌ | ✅ | Standard async pipe |
| `tokio::sync::oneshot` | ❌ | ❌ | (1 message) | Reply-to / completion signal |
| `tokio::sync::broadcast` | ✅ | ✅ | ✅ | Pub/sub, all receivers see all messages |
| `tokio::sync::watch` | ✅ | ✅ | (latest only) | State updates — only the latest matters |
| `flume` | ✅ | ✅ | ✅ | Multi-producer multi-consumer when you need it |

### `oneshot` for request/response

```rust
async fn ask(actor: &mpsc::Sender<Request>) -> Response {
    let (tx, rx) = oneshot::channel();
    actor.send(Request { reply: tx, ..req }).await.unwrap();
    rx.await.expect("actor dropped")
}
```

### `watch` for "current value" patterns

```rust
let (tx, mut rx) = watch::channel(Config::default());

// Producer
tx.send(new_config).unwrap();

// Consumer — sees only the latest config
while rx.changed().await.is_ok() {
    let config = rx.borrow().clone();
    apply(config);
}
```

---

## `async fn` in Traits (Stable since Rust 1.75)

```rust
// ✅ Stable async traits — works for most cases
trait Storage {
    async fn get(&self, key: &str) -> Option<Vec<u8>>;
    async fn put(&self, key: &str, value: Vec<u8>);
}

impl Storage for InMemory { /* ... */ }
```

**Caveats:**
- Returned futures are **not** `Send` by default. To require `Send`:

```rust
trait Storage: Send + Sync {
    fn get(&self, key: &str) -> impl Future<Output = Option<Vec<u8>>> + Send;
    fn put(&self, key: &str, value: Vec<u8>) -> impl Future<Output = ()> + Send;
}
```

- Trait objects (`dyn Storage`) are **not** supported with native `async fn` yet — use the `async-trait` crate when you need `dyn`:

```rust
use async_trait::async_trait;

#[async_trait]
trait Storage: Send + Sync {
    async fn get(&self, key: &str) -> Option<Vec<u8>>;
}

let stores: Vec<Box<dyn Storage>> = vec![/* ... */];  // works with async-trait
```

---

## Streams

```rust
use futures::stream::{self, StreamExt, TryStreamExt};

// Process items concurrently with bounded parallelism
let results: Vec<Output> = stream::iter(items)
    .map(|item| async move { process(item).await })
    .buffer_unordered(10)  // up to 10 in flight
    .try_collect()
    .await?;
```

```rust
// Async iteration with try_for_each
stream::iter(jobs)
    .map(Ok)  // wrap in Result for try_*
    .try_for_each_concurrent(8, |job| async move { run(job).await })
    .await?;
```

---

## `tokio::main` and Runtime Choice

```rust
// ✅ Default — multi-threaded runtime
#[tokio::main]
async fn main() -> Result<()> { /* ... */ }

// ✅ Single-threaded when you want no Send bounds (CLI tools, embedded UI)
#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<()> { /* ... */ }

// ✅ Explicit configuration
fn main() -> Result<()> {
    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(4)
        .enable_all()
        .build()?;
    rt.block_on(async { /* ... */ })
}
```

**Single-threaded runtime advantages:**
- No `Send` bound required on futures
- Can use `Rc<T>` and `RefCell<T>` freely
- Simpler debugging
- Use for: GUI event loops, CLI tools, single-tenant servers

---

## Common Pitfalls

### Forgetting `.await`

```rust
// ❌ Compiles, does nothing — futures are lazy
async fn warm_up() {
    fetch_initial_data();  // missing .await — this is a no-op
}

// ✅ clippy::let_underscore_future catches `let _ = fut;`
async fn warm_up() {
    fetch_initial_data().await;
}
```

Enable `#![warn(unused_must_use)]` and `clippy::let_underscore_future`.

### Spawning without keeping the handle

```rust
// ❌ Task is spawned but if it errors, nobody knows
tokio::spawn(async move { background_work().await });

// ✅ Either await it
tokio::spawn(async move {
    if let Err(e) = background_work().await {
        tracing::error!(error = %e, "background_work failed");
    }
});

// ✅ Or use a JoinSet to collect outcomes
```

### Async recursion

```rust
// ❌ Won't compile — async recursion creates an infinite-size future
async fn walk(node: &Node) {
    for child in &node.children {
        walk(child).await;
    }
}

// ✅ Box the recursive future
fn walk<'a>(node: &'a Node) -> Pin<Box<dyn Future<Output = ()> + Send + 'a>> {
    Box::pin(async move {
        for child in &node.children {
            walk(child).await;
        }
    })
}
```

The `async-recursion` crate macro hides the boxing.

---

## Tracing in Async Code

```rust
use tracing::{info, instrument};

#[instrument(skip(client), fields(user_id = %req.user_id))]
async fn handle(req: Request, client: &Client) -> Result<Response, Error> {
    info!("handling request");
    let user = client.fetch_user(req.user_id).await?;
    Ok(Response::from(user))
}
```

`#[instrument]` automatically:
- Creates a span around the function
- Includes function args (skip large/sensitive ones)
- Records the span across `.await` boundaries

---

## Quick Checklist

- [ ] No `std::fs`, `std::net`, `std::thread::sleep`, or sync channel `.recv()` in `async fn`
- [ ] `tokio::task::spawn_blocking` for CPU-bound > 10ms
- [ ] No `std::sync::Mutex` held across `.await` — drop scope or use `tokio::sync::Mutex`
- [ ] Default to `std::sync::Mutex`; reach for `tokio::sync::Mutex` only when needed
- [ ] `Arc<T>` not `Rc<T>` for anything spawned on multi-thread runtime
- [ ] Spawned tasks: error logged or `JoinHandle`/`JoinSet` collected
- [ ] `select!` arms are cancel-safe (check the docs)
- [ ] `CancellationToken` for graceful shutdown
- [ ] Right channel for the job (`oneshot` for replies, `watch` for state, `mpsc` for streams)
- [ ] `#[instrument]` on async entry points
- [ ] Single-threaded runtime when you can — simpler bounds
