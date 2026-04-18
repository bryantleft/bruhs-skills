# Python + FastAPI Best Practices

FastAPI on Python 3.13+ with Pydantic v2, async SQLAlchemy 2.0, and modern dependency injection. Loaded by `cook` and `slop` when `framework: fastapi` is detected. Builds on `practices/python.md`.

Sources: official [FastAPI docs](https://fastapi.tiangolo.com/), [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) (a widely cited industry reference), and [SQLAlchemy 2.0 docs](https://docs.sqlalchemy.org/en/20/).

---

## Mental Model

> **Type hints are the architecture, not annotations.** FastAPI reads them to generate validation, docs, dependency wiring, and the OpenAPI schema. If you skip them, you've turned off the framework.

Three layers, kept distinct:

| Layer | Purpose | Type |
|-------|---------|------|
| **Schemas** | Validate I/O at the HTTP boundary | Pydantic `BaseModel` |
| **Models** | Persisted entities | SQLAlchemy `DeclarativeBase` |
| **Services** | Business logic | Plain functions / classes, take dependencies as args |

The same shape often appears in all three (User schema vs User model vs User service). Don't merge them — divergence is the rule, and merging hides it.

---

## Project Structure

```
app/
├── main.py                       # FastAPI app instance + global setup
├── config.py                     # Pydantic Settings
├── deps.py                       # Cross-cutting Depends() factories
├── exceptions.py                 # Custom exception types + handlers
├── routers/
│   ├── __init__.py
│   ├── users.py                  # APIRouter for /users
│   └── orders.py                 # APIRouter for /orders
├── schemas/
│   ├── user.py                   # Pydantic request/response models
│   └── order.py
├── models/                       # SQLAlchemy
│   ├── __init__.py
│   ├── base.py                   # DeclarativeBase
│   ├── user.py
│   └── order.py
├── services/                     # Business logic
│   ├── user_service.py
│   └── order_service.py
└── db.py                         # Async session factory
tests/
└── ...
```

This layout scales from a few endpoints to a few hundred without renaming files.

---

## Pillar 1: Routers, Not Decorators on `app`

```python
# ❌ Everything on the app — doesn't scale
from fastapi import FastAPI
app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int): ...

# ✅ APIRouter per resource, mounted in main
# routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    user = await service.find(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return user

# main.py
from fastapi import FastAPI
from app.routers import users, orders
app = FastAPI()
app.include_router(users.router)
app.include_router(orders.router)
```

`tags` group endpoints in the auto-generated `/docs` UI. `prefix` keeps URL building DRY.

---

## Pillar 2: Schema Discipline

### Separate request from response

```python
# schemas/user.py
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class UserCreate(BaseModel):
    """Body of POST /users — what the client sends."""
    email: EmailStr
    password: str = Field(min_length=8)
    age: int = Field(gt=0, lt=150)

class UserResponse(BaseModel):
    """What we return — never includes password hash."""
    id: int
    email: EmailStr
    age: int
    created_at: datetime

    model_config = {"from_attributes": True}  # accepts ORM objects directly

class UserUpdate(BaseModel):
    """PATCH /users/{id} — all fields optional."""
    email: EmailStr | None = None
    age: int | None = Field(default=None, gt=0, lt=150)
```

`from_attributes = True` (the v2 replacement for v1's `orm_mode`) lets you `UserResponse.model_validate(user_orm_obj)`.

### Never reuse models for both directions

```python
# ❌ Same model for input and output — leaks password back to client
class User(BaseModel):
    email: str
    password: str   # this comes back in responses!

@app.post("/users")
async def create_user(user: User) -> User: ...

# ✅ Distinct types per direction
@app.post("/users", response_model=UserResponse)
async def create_user(payload: UserCreate) -> UserResponse: ...
```

### Strict mode on external-facing models

```python
class WebhookPayload(BaseModel):
    model_config = {"strict": True, "extra": "forbid"}
    # strict: no coercion ("1" stays a string, doesn't become int)
    # extra=forbid: reject unknown fields (typo protection)
```

---

## Pillar 3: Dependency Injection

`Depends()` is FastAPI's superpower. Use it for *everything* that crosses a boundary.

### Database session (async SQLAlchemy 2.0)

```python
# db.py
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session

# routers/users.py
@router.get("/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await db.get(User, user_id)
    ...
```

### Composing dependencies

```python
# Auth dependency that reuses get_db
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_jwt(token)
    user = await db.get(User, payload.user_id)
    if not user:
        raise HTTPException(401, "invalid token")
    return user

# Endpoints just compose
@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)

# Role-required dep, built on top
async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "admin only")
    return user

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    ...
```

### `Annotated` for reusable dep aliases (modern style)

```python
from typing import Annotated
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]

@router.get("/me")
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, _: AdminUser, db: DbSession) -> None:
    ...
```

This is the **2026 idiom** — it scales beautifully and reads cleanly.

---

## Pillar 4: Async Database

### SQLAlchemy 2.0 async style

```python
# models/user.py
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    age: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

`Mapped[T]` is the typed declarative style introduced in SQLAlchemy 2.0. Type checkers see the column types correctly.

### Queries — `select` API, not the legacy `Query`

```python
from sqlalchemy import select

# ❌ Legacy 1.x Query API
users = db.query(User).filter(User.age > 18).all()

# ✅ 2.0 select() — works with async
result = await db.execute(select(User).where(User.age > 18))
users = result.scalars().all()

# ✅ Single row
user = await db.scalar(select(User).where(User.email == "alice@example.com"))
```

### Avoid N+1 with `selectinload` / `joinedload`

```python
from sqlalchemy.orm import selectinload

# ❌ N+1 — one extra query per user.posts access
users = await db.scalars(select(User))
for user in users:
    print(user.posts)  # triggers separate SELECT

# ✅ Eagerly load
users = await db.scalars(select(User).options(selectinload(User.posts)))
for user in users:
    print(user.posts)  # already loaded
```

### Transactions

```python
async def transfer(db: AsyncSession, from_id: int, to_id: int, amount: int) -> None:
    async with db.begin():           # commits on exit, rolls back on exception
        from_acct = await db.get(Account, from_id, with_for_update=True)
        to_acct = await db.get(Account, to_id, with_for_update=True)
        from_acct.balance -= amount
        to_acct.balance += amount
```

---

## Pillar 5: Error Handling

### Custom exceptions per domain

```python
# exceptions.py
class AppError(Exception):
    """Base for all app-defined exceptions."""
    status_code: int = 500
    message: str = "internal error"

class NotFoundError(AppError):
    status_code = 404

class UserNotFound(NotFoundError):
    def __init__(self, user_id: int) -> None:
        self.message = f"user {user_id} not found"
        super().__init__(self.message)

class ValidationError(AppError):
    status_code = 422
```

### Translate to HTTP via an exception handler

```python
# main.py
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.__class__.__name__, "message": exc.message},
    )
```

Now services raise plain `UserNotFound(42)`, and the HTTP shape happens automatically.

### Don't catch and re-raise as HTTPException at every layer

```python
# ❌ Boilerplate at every layer
async def get_user(user_id: int) -> User:
    user = await repo.find(user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    return user

# ✅ Service raises domain exceptions; handler maps to HTTP
async def get_user(user_id: int) -> User:
    user = await repo.find(user_id)
    if user is None:
        raise UserNotFound(user_id)
    return user
```

---

## Pillar 6: Settings via Pydantic

```python
# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 60
    debug: bool = False

@lru_cache  # cached singleton — read once
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

Use it as a dependency — overridable in tests:

```python
SettingsDep = Annotated[Settings, Depends(get_settings)]

@router.get("/health")
async def health(s: SettingsDep) -> dict[str, str]:
    return {"db": s.database_url, "debug": str(s.debug)}

# In tests:
def override_settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///:memory:", ...)

app.dependency_overrides[get_settings] = override_settings
```

---

## Pillar 7: Background Tasks

### `BackgroundTasks` for short, fire-and-forget work after response

```python
@router.post("/orders")
async def create_order(
    payload: OrderCreate,
    background: BackgroundTasks,
    db: DbSession,
) -> OrderResponse:
    order = await create_order_service(db, payload)
    background.add_task(send_confirmation_email, order.id)
    return OrderResponse.model_validate(order)
```

`BackgroundTasks` runs **in the same process** after the response is sent. Fine for small things (sending an email, logging an event). NOT a substitute for a real queue.

### For real async work — Celery / RQ / Arq / Temporal

```python
# Use a dedicated queue for anything that:
# - Takes more than a few seconds
# - Must survive process restart
# - Needs retry logic, scheduling, or fan-out
```

Don't reach for `asyncio.create_task(work)` to "run in the background" — the task disappears with the request and you'll never know it failed.

---

## Pillar 8: Testing

### Async test client

```python
# conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.deps import get_db

@pytest.fixture
async def client(db_session):
    async def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
```

```python
# tests/test_users.py
async def test_create_user_returns_201(client, db_session):
    response = await client.post("/users", json={
        "email": "alice@example.com", "password": "supersecret", "age": 30,
    })
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "password" not in body
```

### Override dependencies, not patch internals

```python
# ❌ Brittle — couples test to implementation
@patch("app.services.user_service.send_email")
def test_signup_sends_email(...): ...

# ✅ Override the dependency
def fake_email_sender():
    return Mock()

app.dependency_overrides[get_email_sender] = fake_email_sender
```

---

## Pillar 9: Observability

### Structured logging

```python
import structlog
log = structlog.get_logger()

log.info("user created", user_id=user.id, email=user.email)
# → {"event": "user created", "user_id": 42, "email": "...", "timestamp": "..."}
```

### Request middleware for request ID + timing

```python
from fastapi import Request
import time, uuid

@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
    start = time.perf_counter()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        log.info("request", method=request.method, path=request.url.path,
                 status=response.status_code, duration_ms=round(duration_ms, 2))
        response.headers["x-request-id"] = request_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()
```

### OpenTelemetry for traces

```sh
uv add opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-sqlalchemy
```

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine)
```

---

## Pillar 10: Production Concerns

| Concern | Choice |
|---------|--------|
| Server | `uvicorn` for dev, `gunicorn -w N -k uvicorn.workers.UvicornWorker` for prod |
| Worker count | `2 × CPUs + 1` for I/O-heavy; equal to CPUs for CPU-heavy |
| Connection pool | SQLAlchemy default (5 + 10 overflow) per worker; tune with `pool_size` |
| Migrations | `alembic` — generated from models, hand-edited where needed |
| Health checks | `/health` (liveness) and `/ready` (deps reachable) — distinct |
| Rate limiting | `slowapi` (in-process) or Redis-backed via middleware |
| CORS | `CORSMiddleware` — explicit origins, NOT `*` in production |

---

## Performance Defaults

> **Fast path is the default path.** These aren't optimizations — they're the starting point.

### `ORJSONResponse` as the app default

Stdlib JSON is 2–5× slower than orjson. Make it the app-wide default, not a per-route opt-in:

```python
from fastapi.responses import ORJSONResponse

app = FastAPI(default_response_class=ORJSONResponse)
```

### Eager-load by default; catch lazy loads in dev

Set `lazy="raise"` (or `lazy="raise_on_sql"`) on relationships in the async context, so accidental lazy loads scream instead of N+1ing silently:

```python
class User(Base):
    posts: Mapped[list["Post"]] = relationship(lazy="raise")
```

Then you *must* use `selectinload` / `joinedload` — the compiler does the enforcement.

### Async driver + correctly sized pool

```python
engine = create_async_engine(
    settings.database_url,       # postgresql+asyncpg://...
    pool_size=20,                # default 5 is too low for most apps
    max_overflow=10,
    pool_pre_ping=True,          # drops dead connections
)
```

Size: **`CPU × 2–4`** per worker for I/O-heavy APIs. Too small = queueing. Too large = Postgres gets unhappy around 100-200 connections total.

### `BackgroundTasks` for post-response work

```python
@router.post("/signup")
async def signup(data: SignupIn, bg: BackgroundTasks) -> UserOut:
    user = await create_user(data)
    bg.add_task(send_welcome_email, user.email)  # after response flushes
    return UserOut.model_validate(user)
```

**But**: `BackgroundTasks` runs in the same process. Use Celery / RQ / ARQ for work that *must* succeed or survive a crash.

### `StreamingResponse` for large / NDJSON / SSE

```python
from fastapi.responses import StreamingResponse

@router.get("/export")
async def export_users() -> StreamingResponse:
    async def gen():
        async for user in stream_users():
            yield orjson.dumps(user) + b"\n"
    return StreamingResponse(gen(), media_type="application/x-ndjson")
```

Never buffer large exports into memory.

### Batch database writes

```python
# ❌ N round trips
for row in rows:
    session.add(User(**row))
await session.commit()

# ✅ One round trip
await session.execute(insert(User), rows)
await session.commit()
```

### HTTP client singleton

```python
# app state pattern
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=10.0, limits=httpx.Limits(max_connections=100))
    yield
    await app.state.http.aclose()

app = FastAPI(lifespan=lifespan, default_response_class=ORJSONResponse)
```

### Cache read-heavy endpoints

```python
from fastapi import Response

@router.get("/stats")
async def stats(response: Response) -> StatsOut:
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
    return await compute_stats()
```

For app-level caching, `aiocache` with Redis backend, keyed deterministically by query params.

### Performance Traps

- **Sync libs in async handlers** — `requests`, `bcrypt.hashpw` direct, `time.sleep`, sync SDKs. Use `asyncio.to_thread` or async equivalents.
- **`await` in a `for` loop over independent IDs** — `asyncio.gather` with bounded `Semaphore`.
- **Default `lazy="select"` on async sessions** — raises at access time or N+1s silently. Use `lazy="raise"` + explicit `selectinload`.
- **Creating a new `httpx.AsyncClient` per request.** Lifespan-scoped singleton.
- **Heavy Pydantic validation on internal-only hot paths** — use `msgspec` where you don't need Pydantic's ecosystem features.
- **Full-body request/response logging.** JSON serialization dominates CPU under load. Log structured fields + sample bodies.

### Performance Checklist

- [ ] `ORJSONResponse` as app default
- [ ] Relations `lazy="raise"`; all ORM paths use `selectinload`/`joinedload`
- [ ] Async driver (`asyncpg`); `pool_size` tuned above default 5
- [ ] `StreamingResponse` for exports / NDJSON / SSE
- [ ] `BackgroundTasks` for fire-and-forget post-response work
- [ ] Batched inserts/updates; no row-by-row writes
- [ ] `httpx.AsyncClient` as lifespan singleton
- [ ] Cache-Control headers on cacheable GETs
- [ ] No sync I/O inside async handlers
- [ ] Bounded concurrency on user-driven fan-out
- [ ] `uvloop` + `httptools` under uvicorn

---

## Quick Reference

### Always
- [ ] Type-annotated function signatures everywhere
- [ ] APIRouter per resource, included in `main.py`
- [ ] Distinct request/response Pydantic models — never share
- [ ] `model_config = {"strict": True, "extra": "forbid"}` for external models
- [ ] Dependencies via `Annotated[T, Depends(...)]` aliases
- [ ] Async SQLAlchemy 2.0 with `Mapped[T]` typed columns and `select()` API
- [ ] Domain exceptions + global handler — no `HTTPException` in services
- [ ] `Pydantic Settings` for config, exposed as a dep with `@lru_cache`
- [ ] Structured logging (`structlog`); request-id middleware
- [ ] `ORJSONResponse` as app default; lazy=`raise` on relationships

### Avoid
- [ ] Same model for request + response
- [ ] N+1 queries (`selectinload`/`joinedload`)
- [ ] `@app.<verb>` decorators in `main.py` for actual endpoints (use routers)
- [ ] `BackgroundTasks` for anything that must succeed
- [ ] Catching exceptions just to re-raise as `HTTPException`
- [ ] CORS `*` in production
- [ ] Sync libs inside async handlers; per-request HTTP client construction

### Tooling
- [ ] `uv` for env + deps
- [ ] `ruff` lint + format
- [ ] `ty` (or strict `mypy`) on every public surface
- [ ] `pytest` + `pytest-asyncio` (auto mode) + `httpx.AsyncClient`
- [ ] `alembic` for migrations
- [ ] OTel instrumentation in production

---

## References

- [FastAPI docs](https://fastapi.tiangolo.com/) — official, kept current
- [SQLAlchemy 2.0 docs](https://docs.sqlalchemy.org/en/20/) — async + typed mapping
- [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) — battle-tested startup patterns
- [Pydantic v2 docs](https://docs.pydantic.dev/latest/)
