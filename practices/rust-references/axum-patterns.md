# Axum Patterns

Best practices for [Axum 0.8](https://docs.rs/axum) — Tokio's web framework. Loaded by `cook` and `slop` when `axum` appears in `Cargo.toml`. Builds on `practices/rust.md` and `practices/rust-references/async-patterns.md`.

Sources: [official axum docs](https://docs.rs/axum/latest/axum/), [tokio-rs/axum examples](https://github.com/tokio-rs/axum/tree/main/examples), and the Tower middleware ecosystem docs.

---

## Mental Model

> **Axum is a thin layer over Tower. Handlers are just async functions whose arguments and return types implement specific traits. Errors must be handled inside the service tree — Axum requires `Infallible` at the leaf.**

Three concepts compose Axum:

| Concept | What | Example |
|---------|------|---------|
| **Extractor** | A type that pulls something out of the request | `Path<T>`, `Query<T>`, `Json<T>`, `State<T>`, custom |
| **Handler** | An `async fn` that takes extractors and returns something `IntoResponse` | `async fn list(State(db): State<Db>) -> Json<Vec<User>>` |
| **Router** | A typed map of paths/methods to handlers | `Router::new().route("/users", get(list).post(create))` |

Axum delegates HTTP serving to [`hyper`](https://docs.rs/hyper) and middleware to [`tower`](https://docs.rs/tower) / [`tower-http`](https://docs.rs/tower-http) — so anything in those ecosystems plugs in.

---

## Project Structure

```
src/
├── main.rs                # tokio::main, build router, bind socket
├── state.rs               # AppState struct
├── error.rs               # AppError + IntoResponse impl
├── routes/
│   ├── mod.rs             # Router::new() compositions
│   ├── users.rs
│   └── orders.rs
├── extractors/            # Custom extractors (auth, request id, etc.)
│   └── auth.rs
├── middleware/
│   └── trace.rs
├── models/                # Domain types
│   └── user.rs
└── services/              # Business logic
    └── user_service.rs
```

---

## Pillar 1: Application State via `State<T>`

```rust
// state.rs
use std::sync::Arc;
use sqlx::PgPool;

#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,
    pub config: Arc<Config>,
}
```

`AppState` must be `Clone` (Axum clones it per request). Heavy data goes behind `Arc`.

```rust
// main.rs
let state = AppState {
    db: PgPool::connect(&env::var("DATABASE_URL")?).await?,
    config: Arc::new(Config::load()?),
};

let app = Router::new()
    .route("/users/:id", get(get_user))
    .with_state(state);

let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await?;
axum::serve(listener, app).await?;
```

```rust
// routes/users.rs — extract state by destructuring
async fn get_user(
    State(state): State<AppState>,
    Path(user_id): Path<i64>,
) -> Result<Json<User>, AppError> {
    let user = sqlx::query_as!(User, "SELECT * FROM users WHERE id = $1", user_id)
        .fetch_optional(&state.db)
        .await?
        .ok_or(AppError::NotFound)?;
    Ok(Json(user))
}
```

### Substate (Axum 0.7+)

Avoid passing the whole `AppState` when a handler needs only one thing:

```rust
// state.rs
impl FromRef<AppState> for PgPool {
    fn from_ref(state: &AppState) -> Self { state.db.clone() }
}
impl FromRef<AppState> for Arc<Config> {
    fn from_ref(state: &AppState) -> Self { state.config.clone() }
}

// handler — extracts only what it needs
async fn get_user(
    State(db): State<PgPool>,
    Path(user_id): Path<i64>,
) -> Result<Json<User>, AppError> { /* ... */ }
```

This is the **2026 idiom**. It keeps handlers honest about their dependencies and makes them trivially testable.

---

## Pillar 2: Errors Must Implement `IntoResponse`

> Axum requires every service to have `Infallible` as its error type at the leaf. Your handler error must convert to a response, not propagate.

```rust
// error.rs
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::json;

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("not found")]
    NotFound,

    #[error("unauthorized")]
    Unauthorized,

    #[error("validation: {0}")]
    Validation(String),

    #[error(transparent)]
    Db(#[from] sqlx::Error),

    #[error(transparent)]
    Internal(#[from] anyhow::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code) = match &self {
            AppError::NotFound => (StatusCode::NOT_FOUND, "not_found"),
            AppError::Unauthorized => (StatusCode::UNAUTHORIZED, "unauthorized"),
            AppError::Validation(_) => (StatusCode::UNPROCESSABLE_ENTITY, "validation"),
            AppError::Db(e) => {
                tracing::error!(error = %e, "database error");
                (StatusCode::INTERNAL_SERVER_ERROR, "internal")
            }
            AppError::Internal(e) => {
                tracing::error!(error = %e, "internal error");
                (StatusCode::INTERNAL_SERVER_ERROR, "internal")
            }
        };

        (status, Json(json!({ "error": code, "message": self.to_string() }))).into_response()
    }
}
```

Now `Result<T, AppError>` is a valid handler return type — `?` works inside handlers.

### Don't return `Box<dyn Error>` from handlers

It compiles but loses every chance to map the error to a sensible status code. Always use a concrete error enum.

---

## Pillar 3: Extractors — Custom Where Useful

Built-ins cover most needs:

| Extractor | Purpose |
|-----------|---------|
| `Path<T>` | URL params (`/users/:id` → `Path<i64>`) |
| `Query<T>` | Query string (`?limit=10` → `Query<Pagination>` where `Pagination: Deserialize`) |
| `Json<T>` | JSON body, parsed with serde + 422 on parse fail |
| `Form<T>` | URL-encoded form body |
| `State<T>` | Application state (or substate via `FromRef`) |
| `Extension<T>` | Per-request data injected by middleware (use sparingly) |
| `Request<Body>` | Full request — for low-level access |

### Custom extractor for the current user

```rust
// extractors/auth.rs
use axum::{async_trait, extract::FromRequestParts, http::request::Parts};

pub struct AuthUser(pub User);

#[async_trait]
impl<S> FromRequestParts<S> for AuthUser
where
    S: Send + Sync,
    PgPool: FromRef<S>,
{
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        let token = parts
            .headers
            .get("authorization")
            .and_then(|v| v.to_str().ok())
            .and_then(|s| s.strip_prefix("Bearer "))
            .ok_or(AppError::Unauthorized)?;

        let claims = decode_jwt(token).map_err(|_| AppError::Unauthorized)?;
        let db = PgPool::from_ref(state);
        let user = sqlx::query_as!(User, "SELECT * FROM users WHERE id = $1", claims.sub)
            .fetch_optional(&db)
            .await?
            .ok_or(AppError::Unauthorized)?;

        Ok(AuthUser(user))
    }
}

// Usage — auth happens just by adding the extractor
async fn get_me(AuthUser(user): AuthUser) -> Json<User> { Json(user) }
```

This is much cleaner than middleware that injects via `Extension<User>` — the handler signature literally tells you "this requires auth."

---

## Pillar 4: Routing

```rust
use axum::{Router, routing::{get, post, delete}};

let api = Router::new()
    .route("/users", get(list_users).post(create_user))
    .route("/users/:id", get(get_user).patch(update_user).delete(delete_user))
    .route("/users/:id/orders", get(list_user_orders));

let app = Router::new()
    .nest("/api/v1", api)
    .nest_service("/static", ServeDir::new("static"))   // tower-http static files
    .layer(TraceLayer::new_for_http())
    .layer(CorsLayer::permissive())                      // tighter in prod
    .with_state(state);
```

### `nest` for sub-routers, `merge` for siblings

```rust
let users_router = Router::new()
    .route("/", get(list).post(create))
    .route("/:id", get(get_one).delete(delete_one));

let app = Router::new()
    .nest("/users", users_router)        // mounts at /users
    .merge(other_router)                 // merges into root
    .with_state(state);
```

---

## Pillar 5: Middleware via Tower

Two ways to write middleware. Pick by what it does:

### `from_fn` — for request/response mutation

```rust
use axum::{middleware, http::Request, response::Response};
use std::time::Instant;

async fn timing_middleware(req: Request<axum::body::Body>, next: middleware::Next) -> Response {
    let start = Instant::now();
    let path = req.uri().path().to_owned();
    let method = req.method().clone();

    let response = next.run(req).await;

    tracing::info!(
        method = %method,
        path = %path,
        status = response.status().as_u16(),
        elapsed_ms = start.elapsed().as_millis(),
        "request"
    );
    response
}

let app = Router::new()
    .route("/users", get(list_users))
    .layer(middleware::from_fn(timing_middleware));
```

### `from_extractor` — when you have an extractor that's also useful as gating

```rust
let app = Router::new()
    .route("/admin", get(admin_dashboard))
    .layer(middleware::from_extractor::<RequireAdmin>());
```

### Tower layers — for everything else

```rust
use tower_http::{
    cors::CorsLayer,
    compression::CompressionLayer,
    timeout::TimeoutLayer,
    trace::TraceLayer,
    request_id::SetRequestIdLayer,
};
use std::time::Duration;

let app = Router::new()
    /* routes */
    .layer(TraceLayer::new_for_http())
    .layer(CompressionLayer::new())
    .layer(TimeoutLayer::new(Duration::from_secs(30)))
    .layer(CorsLayer::new()
        .allow_origin(["https://app.example.com".parse().unwrap()])
        .allow_methods([Method::GET, Method::POST]));
```

### `HandleErrorLayer` for fallible middleware

Tower middleware can have non-`Infallible` error types. Convert them via `HandleErrorLayer`:

```rust
use axum::error_handling::HandleErrorLayer;
use tower::ServiceBuilder;

let app = Router::new()
    .route("/", get(handler))
    .layer(
        ServiceBuilder::new()
            .layer(HandleErrorLayer::new(|err: BoxError| async move {
                if err.is::<tower::timeout::error::Elapsed>() {
                    (StatusCode::REQUEST_TIMEOUT, "timeout".to_string())
                } else {
                    (StatusCode::INTERNAL_SERVER_ERROR, format!("internal: {err}"))
                }
            }))
            .timeout(Duration::from_secs(10))
    );
```

### Layer ordering — outermost first

```rust
let app = Router::new()
    .route("/", get(handler))
    .layer(timing)        // runs LAST (innermost)
    .layer(auth)          // runs SECOND
    .layer(trace);        // runs FIRST (outermost)
```

Think of `.layer()` as wrapping — each call wraps the entire stack underneath. The first `.layer()` you add is closest to the handler.

`.route_layer(...)` applies only to that route's handlers (good for per-route auth) instead of the whole router.

---

## Pillar 6: Validation

Axum's `Json<T>` validates that the body is valid JSON for `T`'s shape, but doesn't enforce business rules (length, ranges). Combine with a validator like [`validator`](https://docs.rs/validator) or [`garde`](https://docs.rs/garde).

```rust
use validator::Validate;
use serde::Deserialize;

#[derive(Deserialize, Validate)]
pub struct CreateUser {
    #[validate(email)]
    pub email: String,

    #[validate(length(min = 8))]
    pub password: String,

    #[validate(range(min = 1, max = 150))]
    pub age: u32,
}

async fn create_user(
    State(db): State<PgPool>,
    Json(payload): Json<CreateUser>,
) -> Result<Json<User>, AppError> {
    payload.validate().map_err(|e| AppError::Validation(e.to_string()))?;
    /* ... */
}
```

For repeated patterns, build a custom `ValidatedJson<T>` extractor:

```rust
pub struct ValidatedJson<T>(pub T);

#[async_trait]
impl<S, T> FromRequest<S> for ValidatedJson<T>
where
    S: Send + Sync,
    T: DeserializeOwned + Validate,
{
    type Rejection = AppError;

    async fn from_request(req: Request, state: &S) -> Result<Self, Self::Rejection> {
        let Json(value) = Json::<T>::from_request(req, state)
            .await
            .map_err(|e| AppError::Validation(e.to_string()))?;
        value.validate().map_err(|e| AppError::Validation(e.to_string()))?;
        Ok(ValidatedJson(value))
    }
}

// Now handlers just say:
async fn create_user(
    State(db): State<PgPool>,
    ValidatedJson(payload): ValidatedJson<CreateUser>,
) -> Result<Json<User>, AppError> { /* ... */ }
```

---

## Pillar 7: Database — sqlx + connection pooling

```rust
use sqlx::postgres::{PgPool, PgPoolOptions};

let db = PgPoolOptions::new()
    .max_connections(20)
    .min_connections(2)
    .acquire_timeout(Duration::from_secs(3))
    .connect(&env::var("DATABASE_URL")?)
    .await?;

sqlx::migrate!("./migrations").run(&db).await?;
```

### Compile-time checked queries

```rust
// query_as! validates the query and column types at compile time against the live DB
let user = sqlx::query_as!(
    User,
    "SELECT id, email, age FROM users WHERE id = $1",
    user_id
)
.fetch_optional(&db)
.await?;
```

This requires the database to be reachable during `cargo check` (or pre-cached via `cargo sqlx prepare`).

### Transactions

```rust
let mut tx = db.begin().await?;
sqlx::query!("UPDATE accounts SET balance = balance - $1 WHERE id = $2", amount, from)
    .execute(&mut *tx).await?;
sqlx::query!("UPDATE accounts SET balance = balance + $1 WHERE id = $2", amount, to)
    .execute(&mut *tx).await?;
tx.commit().await?;
```

---

## Pillar 8: Tracing & Observability

```rust
use tower_http::trace::{TraceLayer, DefaultMakeSpan, DefaultOnResponse};
use tracing::Level;

tracing_subscriber::fmt()
    .with_env_filter("info,sqlx=warn,tower_http=debug")
    .json()
    .init();

let app = Router::new()
    /* routes */
    .layer(
        TraceLayer::new_for_http()
            .make_span_with(DefaultMakeSpan::new().level(Level::INFO))
            .on_response(DefaultOnResponse::new().level(Level::INFO))
    );
```

`#[instrument]` on async handlers integrates beautifully:

```rust
#[tracing::instrument(skip(db), fields(user_id = %user_id))]
async fn get_user(
    State(db): State<PgPool>,
    Path(user_id): Path<i64>,
) -> Result<Json<User>, AppError> { /* spans automatically include user_id */ }
```

---

## Pillar 9: Graceful Shutdown

```rust
async fn shutdown_signal() {
    let ctrl_c = async {
        tokio::signal::ctrl_c().await.expect("install SIGINT handler");
    };

    #[cfg(unix)]
    let terminate = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("install SIGTERM handler")
            .recv()
            .await;
    };

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
    tracing::info!("shutdown signal received");
}

let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await?;
axum::serve(listener, app)
    .with_graceful_shutdown(shutdown_signal())
    .await?;
```

---

## Pillar 10: Testing

```rust
use axum::body::Body;
use axum::http::{Request, StatusCode};
use tower::ServiceExt;            // for `oneshot`

#[tokio::test]
async fn get_user_returns_200_for_existing_user() {
    let state = test_state().await;
    let app = build_router(state);

    let response = app
        .oneshot(
            Request::builder()
                .uri("/users/1")
                .body(Body::empty())
                .unwrap()
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let body = axum::body::to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let user: User = serde_json::from_slice(&body).unwrap();
    assert_eq!(user.id, 1);
}
```

`oneshot` consumes the router and runs a single request — no HTTP server, no port allocation, no flakes. Pair with a `test_state()` fixture that spins up an in-memory or test database (`sqlx::test` macro automates this).

---

## Quick Reference

### Always
- [ ] `AppState: Clone`; heavy data behind `Arc`
- [ ] `FromRef<AppState>` for substate so handlers extract only what they need
- [ ] Concrete `AppError` enum implementing `IntoResponse`; `?` works in handlers
- [ ] Custom extractors for cross-cutting concerns (auth, request id) — preferred over `Extension<T>` middleware
- [ ] Validate inputs with `validator` / `garde` (often via a `ValidatedJson<T>` extractor)
- [ ] Tower layers for cross-cutting: `TraceLayer`, `CompressionLayer`, `TimeoutLayer`, `CorsLayer`
- [ ] `HandleErrorLayer` for fallible middleware
- [ ] `#[tracing::instrument]` on handlers; structured logging
- [ ] `with_graceful_shutdown` on `axum::serve`
- [ ] sqlx `query_as!` for compile-time-checked queries

### Avoid
- [ ] `Box<dyn Error>` as handler error type (use a concrete enum)
- [ ] `Extension<T>` middleware when a custom extractor would be clearer
- [ ] CORS `permissive()` in production
- [ ] Heavy state cloned per request (`Arc` it)
- [ ] Holding sync `Mutex` across `.await` (see `practices/rust-references/async-patterns.md`)

### Testing
- [ ] `tower::ServiceExt::oneshot` over spinning a real server
- [ ] `sqlx::test` macro for transactional test isolation
- [ ] Override state per test (test-only `FromRef` impls)

---

## References

- [axum docs](https://docs.rs/axum/latest/axum/) — official API reference
- [axum/examples](https://github.com/tokio-rs/axum/tree/main/examples) — canonical patterns
- [axum::error_handling docs](https://docs.rs/axum/latest/axum/error_handling/index.html)
- [tower-http](https://docs.rs/tower-http) — middleware catalog
- [sqlx docs](https://docs.rs/sqlx) — async DB
