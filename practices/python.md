# Python Best Practices

Modern Python (3.12+ targeting 3.13). Reflects the 2026 tooling consolidation around Astral's stack (uv + ruff + ty) and the maturation of typed Python. Cribbed from the Python core docs, [Hynek Schlawack](https://hynek.me/articles/), [Raymond Hettinger](https://rhettinger.github.io/), [Pydantic](https://docs.pydantic.dev/) and [FastAPI](https://fastapi.tiangolo.com/) docs, and the [PEP](https://peps.python.org/) standards.

**Used by:**
- `cook` — patterns to follow when building Python features
- `slop` — patterns to detect during cleanup

**Stack triggers:** `language: python` or any Python framework (`fastapi`, `django`, `flask`, etc.) in `bruhs.json`.

---

## The 2026 Tooling Stack

Three tools from one company (Astral) replace the old fragmented chain:

| Job | Tool | Replaces |
|-----|------|----------|
| Package + project + venv management | **uv** | pip, pip-tools, poetry, pyenv, virtualenv, pipx |
| Lint + format | **ruff** | black, isort, flake8, pyupgrade, autoflake |
| Type check | **ty** (Astral) or **mypy** | mypy alone |
| Test | **pytest** | unittest |

```sh
uv init                              # new project
uv add fastapi pydantic              # add deps (writes pyproject.toml + uv.lock)
uv add --dev pytest ruff ty          # dev deps
uv run pytest                        # run anything in the project venv
uv sync                              # install lockfile (CI)
uv pip compile --upgrade             # bump deps
```

**Single source of truth: `pyproject.toml`.** Configure ruff, ty, pytest, and packaging metadata in one file. No more `setup.py`, `requirements.txt`, `setup.cfg`, `.flake8`, `mypy.ini`, `tox.ini` scattered across the repo.

```toml
[project]
name = "myproject"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["fastapi>=0.115", "pydantic>=2.10"]

[tool.uv]
dev-dependencies = ["pytest>=8", "ruff>=0.6", "ty>=0.1"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = [
  "E",    # pycodestyle errors
  "F",    # pyflakes
  "I",    # isort
  "B",    # bugbear
  "UP",   # pyupgrade
  "SIM",  # simplify
  "RUF",  # ruff-specific
  "TID",  # tidy imports
  "TC",   # type-checking imports
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = ["--strict-markers", "-ra"]
```

---

## Pillar 1: Types Are Mandatory

> **Untyped Python is legacy Python.** Annotate every function signature; let inference fill in locals.

Modern type system (Python 3.12+):

### PEP 695 — type parameter syntax (3.12+)

```python
# ❌ Old TypeVar dance
from typing import TypeVar
T = TypeVar("T")
def first(items: list[T]) -> T | None: ...

# ✅ PEP 695 — generic type parameters in the signature
def first[T](items: list[T]) -> T | None: ...

# ✅ Generic classes
class Cache[K, V]:
    def get(self, key: K) -> V | None: ...

# ✅ Type aliases
type UserId = int
type JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
```

### Built-in collection generics (3.9+)

```python
# ❌ Old typing imports
from typing import List, Dict, Optional
def f(x: List[int]) -> Optional[Dict[str, int]]: ...

# ✅ Built-ins
def f(x: list[int]) -> dict[str, int] | None: ...
```

### Self type (PEP 673, 3.11+)

```python
class Builder:
    def with_name(self, n: str) -> "Self":   # ❌ string forward ref
        ...

from typing import Self

class Builder:
    def with_name(self, n: str) -> Self:     # ✅ explicit
        self.name = n
        return self
```

### `Annotated` for metadata

```python
from typing import Annotated
from pydantic import Field

UserId = Annotated[int, Field(gt=0, description="Positive user ID")]
```

### Protocols over base classes

```python
# ❌ Forces inheritance
class Storage(ABC):
    @abstractmethod
    def get(self, k: str) -> bytes: ...

class Redis(Storage):  # explicit inheritance required
    def get(self, k: str) -> bytes: ...

# ✅ Structural typing — anything with a matching shape works
from typing import Protocol

class Storage(Protocol):
    def get(self, k: str) -> bytes: ...

class Redis:                       # no inheritance!
    def get(self, k: str) -> bytes: ...

def use(s: Storage) -> bytes:
    return s.get("foo")            # accepts Redis, file objects, fakes, anything
```

### Strict type checking

```toml
# pyproject.toml — for ty (Astral) or mypy
[tool.ty]
python-version = "3.13"
strict = true

[tool.mypy]
python_version = "3.13"
strict = true
warn_unused_ignores = true
warn_redundant_casts = true
disallow_untyped_defs = true
```

---

## Pillar 2: Data Classes / Pydantic / attrs

Pick the right tool for the job:

| Use | When |
|-----|------|
| `@dataclass` (stdlib) | Internal value types, no validation needed |
| **Pydantic v2** `BaseModel` | I/O boundaries — API requests/responses, config loaded from disk, anything from outside the program |
| **attrs** `@define` | Internal classes where you want post-init hooks, `__slots__`, or richer ergonomics than dataclass |

### Pydantic v2 — for I/O

Pydantic v2 is **Rust-backed**. Validation is ~10–50× faster than v1. Model parsing is no longer a perf concern.

```python
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

class CreateUserRequest(BaseModel):
    email: EmailStr
    age: int = Field(gt=0, lt=150)
    created_at: datetime | None = None

# Parse + validate at the boundary
user = CreateUserRequest.model_validate(json_payload)

# Serialize
user.model_dump_json()  # → '{"email": "...", ...}'

# Strict mode — no coercion (e.g. won't turn "1" into 1)
user = CreateUserRequest.model_validate(payload, strict=True)
```

### Field validators (Pydantic v2 syntax)

```python
from pydantic import BaseModel, field_validator

class Config(BaseModel):
    workers: int

    @field_validator("workers")
    @classmethod
    def workers_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("workers must be >= 1")
        return v
```

### `model_config` — type-safe configuration

```python
class Strict(BaseModel):
    model_config = {"frozen": True, "extra": "forbid", "strict": True}
```

### Don't use Pydantic for everything

```python
# ❌ Internal value class — overkill, ~3× slower than dataclass for simple cases
class Point(BaseModel):
    x: float
    y: float

# ✅ dataclass for internal types
from dataclasses import dataclass
@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float
```

`frozen=True` makes it immutable (hashable, safer). `slots=True` saves memory and prevents typos in attribute names.

---

## Pillar 3: Errors

Python idioms for fallible operations:

### Raise specific exceptions

```python
# ❌ Generic Exception
raise Exception("user not found")

# ❌ ValueError that loses the value
raise ValueError("invalid input")

# ✅ Domain-specific, includes the value
class UserNotFound(LookupError):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"user {user_id} not found")
        self.user_id = user_id

raise UserNotFound(42)
```

### Exception groups (PEP 654, 3.11+)

For concurrent operations where multiple things can fail:

```python
# ❌ Old: only the first error survives
results = await asyncio.gather(*tasks)

# ✅ Surface all errors via ExceptionGroup
async with asyncio.TaskGroup() as tg:
    tasks = [tg.create_task(work(i)) for i in range(10)]
# If multiple tasks raise, an ExceptionGroup bundles them all

try:
    ...
except* HTTPError as eg:           # except* matches inside ExceptionGroup
    handle_http_errors(eg.exceptions)
except* ValidationError as eg:
    handle_validation(eg.exceptions)
```

### Don't suppress

```python
# ❌ Silent failure
try:
    do_thing()
except Exception:
    pass

# ❌ Logging without rethrowing for callers who care
try:
    do_thing()
except Exception as e:
    log.error("failed", exc_info=e)

# ✅ Either rethrow or have an explicit fallback
try:
    do_thing()
except SpecificError as e:
    log.warning("falling back", exc_info=e)
    return fallback_value
```

### `contextlib.suppress` for known-safe ignores

```python
# ✅ Explicit "this error is fine"
from contextlib import suppress

with suppress(FileNotFoundError):
    Path("cache.json").unlink()
```

---

## Pillar 4: Async

> **`async def` is structural. Don't mix sync and async carelessly.**

### Use `asyncio.TaskGroup` (3.11+) over `asyncio.gather`

```python
# ❌ gather: cancellation semantics are surprising
results = await asyncio.gather(work_a(), work_b())

# ✅ TaskGroup: structured concurrency, proper cancellation
async with asyncio.TaskGroup() as tg:
    a = tg.create_task(work_a())
    b = tg.create_task(work_b())
# results: a.result(), b.result()  (TaskGroup awaits all)
```

### Don't block the loop

```python
# ❌ requests is sync — blocks the entire event loop
import requests
async def fetch(url: str) -> str:
    return requests.get(url).text

# ✅ httpx with async
import httpx
async def fetch(url: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        return r.text

# ✅ Or push CPU work to a thread
import asyncio
async def hash_password(pw: str) -> str:
    return await asyncio.to_thread(bcrypt.hashpw, pw.encode(), bcrypt.gensalt())
```

### `asyncio.timeout` (3.11+) over `wait_for`

```python
# ✅ Cleaner than wait_for; integrates with TaskGroup
async with asyncio.timeout(5):
    result = await long_call()
```

### Async context managers and iterators

```python
# ✅ async with for resources that need async cleanup
async with aiofiles.open("data.bin", "rb") as f:
    contents = await f.read()

# ✅ async for over async iterators
async for chunk in stream:
    process(chunk)
```

---

## Pillar 5: Idiomatic Python

### Prefer comprehensions and generators

```python
# ❌ Manual loop accumulating into a list
results = []
for x in items:
    if x.active:
        results.append(x.id)

# ✅ Comprehension
results = [x.id for x in items if x.active]

# ✅ Generator when you don't need the full list at once
total = sum(x.amount for x in transactions if x.cleared)
```

### Match statement (3.10+) for structural dispatch

```python
match event:
    case {"type": "click", "x": x, "y": y}:
        handle_click(x, y)
    case {"type": "key", "key": key}:
        handle_key(key)
    case {"type": "scroll", "delta": delta} if delta > 0:
        scroll_up(delta)
    case _:
        log.warning("unknown event: %r", event)
```

### `pathlib` over `os.path`

```python
# ❌ String surgery
import os
config_path = os.path.join(os.path.dirname(__file__), "..", "config", "app.toml")

# ✅ pathlib
from pathlib import Path
config_path = Path(__file__).parent.parent / "config" / "app.toml"
text = config_path.read_text()
```

### f-strings everywhere (and use `=` for debugging)

```python
# ✅ Self-documenting debug f-strings (3.8+)
log.info(f"{user_id=} {request_id=} processing")
# → user_id=42 request_id='abc' processing

# ✅ Format specs work
log.debug(f"latency: {elapsed_ms:.2f}ms")
```

### Walrus operator (3.8+) for read-then-test

```python
# ❌ Two lookups
match = pattern.match(text)
if match:
    process(match)

# ✅ One
if match := pattern.match(text):
    process(match)
```

### Use `dict.get`, `dict.setdefault`, `defaultdict`

```python
# ❌
if user_id in cache:
    val = cache[user_id]
else:
    val = expensive_lookup(user_id)
    cache[user_id] = val

# ✅
val = cache.get(user_id)
if val is None:
    val = cache[user_id] = expensive_lookup(user_id)

# ✅ defaultdict for accumulation patterns
from collections import defaultdict
buckets = defaultdict(list)
for item in items:
    buckets[item.category].append(item)
```

---

## Pillar 6: Testing (pytest)

```python
# tests/test_user.py
import pytest
from myapp.users import create_user, UserNotFound

def test_create_user_returns_persisted_record(db):
    user = create_user(db, email="alice@example.com")
    assert user.id is not None
    assert db.query_one("SELECT email FROM users WHERE id=?", user.id) == "alice@example.com"

def test_create_user_rejects_duplicate_email(db, sample_user):
    with pytest.raises(ValueError, match="already exists"):
        create_user(db, email=sample_user.email)

@pytest.mark.parametrize("bad_email", ["", "no-at-sign", "@nodomain", "spaces in@email.com"])
def test_create_user_rejects_invalid_email(db, bad_email):
    with pytest.raises(ValueError):
        create_user(db, email=bad_email)
```

### Fixtures over setUp/tearDown

```python
@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    yield conn
    conn.close()

@pytest.fixture
def sample_user(db):
    return create_user(db, email="bob@example.com")
```

### Async tests with `pytest-asyncio`

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"     # treat all async test functions as async tests
```

```python
async def test_fetch_returns_data(client):
    result = await client.fetch("/users/1")
    assert result.status == 200
```

### Property-based testing for complex invariants

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers(min_value=0)))
def test_sort_preserves_length(xs: list[int]):
    assert len(sorted(xs)) == len(xs)
```

---

## Pillar 7: Project Structure

```
myproject/
├── pyproject.toml
├── uv.lock
├── README.md
├── src/
│   └── myproject/
│       ├── __init__.py
│       ├── api.py
│       ├── models.py
│       └── services/
│           └── __init__.py
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   └── test_services.py
└── .python-version       # uv reads this
```

The **`src/` layout** prevents `python -c "import myproject"` from accidentally picking up the working directory instead of the installed package. `uv` and `pytest` both handle it natively.

### Imports

PEP 8 + isort/ruff order:

```python
# Standard library
import json
from pathlib import Path

# Third-party
import httpx
from pydantic import BaseModel

# First-party (your project)
from myproject.config import Settings
from myproject.models import User
```

`from x import *` is banned outside `__init__.py` re-exports.

---

## Pillar 8: Tooling Discipline

### Always run

```sh
uv run ruff check .                  # lint
uv run ruff format .                 # format
uv run ty check                      # or: uv run mypy
uv run pytest                        # tests
```

### Pre-commit hook

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.4.18
    hooks:
      - id: uv-lock      # ensures uv.lock matches pyproject.toml
```

### `# type: ignore` requires a code

```python
# ❌ Silent — ignores future regressions too
result = library_call()  # type: ignore

# ✅ Specific — ruff/mypy will warn if the lint stops applying
result = library_call()  # type: ignore[no-untyped-call]
```

---

## Quick Reference

### Always
- [ ] Type annotations on every public function
- [ ] PEP 695 type-parameter syntax for generics (`def f[T](...)`)
- [ ] `list[T]` / `dict[K, V]` / `T | None` (no `typing.List`, `Optional`)
- [ ] `pyproject.toml` is the single config source
- [ ] `uv` for env + deps; `ruff` for lint + format; `ty` or `mypy` strict
- [ ] f-strings (with `=` for debug); `pathlib.Path` over `os.path`
- [ ] `match` for structural dispatch; walrus for read-then-test

### Pydantic / data
- [ ] Pydantic v2 at I/O boundaries; `dataclass(frozen=True, slots=True)` internally
- [ ] `EmailStr`, `HttpUrl`, `Annotated[int, Field(gt=0)]` for constraints
- [ ] `model_config = {"strict": True, "extra": "forbid"}` on external-facing models

### Async
- [ ] `asyncio.TaskGroup` over `gather`
- [ ] `asyncio.timeout` over `wait_for`
- [ ] `httpx` (async) over `requests`; `aiofiles` over sync `open`
- [ ] `asyncio.to_thread` for CPU-bound; never block the loop

### Errors
- [ ] Domain-specific exception classes, never bare `Exception`
- [ ] `ExceptionGroup` + `except*` for parallel work
- [ ] No silent `except: pass`; use `contextlib.suppress(SpecificError)`

### Testing
- [ ] pytest + fixtures + parametrize
- [ ] `pytest-asyncio` with `asyncio_mode = "auto"`
- [ ] `hypothesis` for invariants worth proving

### Layout
- [ ] `src/` layout
- [ ] PEP 8 import order; no `import *`
- [ ] `# type: ignore[code]` not bare ignores

For framework-specific patterns (FastAPI, Django, etc.) → `practices/python-fastapi.md` etc.

---

## References

- [PEP 695 — Type Parameter Syntax](https://peps.python.org/pep-0695/)
- [PEP 654 — Exception Groups and except*](https://peps.python.org/pep-0654/)
- [Hynek Schlawack's articles](https://hynek.me/articles/) — modern Python craft
- [Pydantic v2 docs](https://docs.pydantic.dev/latest/)
- [Astral docs](https://docs.astral.sh/) — uv, ruff, ty
- [Stuart Ellis — Modern Good Practices for Python Development](https://www.stuartellis.name/articles/python-modern-practices/)
