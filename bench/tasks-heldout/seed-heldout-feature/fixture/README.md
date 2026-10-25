# shelf

Lending library API for the office bookshelf: what's on the shelf and who has what.
FastAPI, in-memory (seeded from `data/books.json` when run as a server).

```sh
uv sync
uv run uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
uv run pytest
```

## API

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/books` | | `{ "books": [Book] }` |
| POST | `/books` | `{ "title", "author" }` | `Book` (201) |
| GET | `/books/{id}` | | `Book` |
| POST | `/books/{id}/checkout` | `{ "member" }` | `Book` |
| POST | `/books/{id}/return` | | `Book` |
| GET | `/members/{member}/books` | | `{ "books": [Book] }` checked out by that member |

`Book` is `{ "id", "title", "author", "checked_out_by" }` (`checked_out_by` is null while
the book is on the shelf). Members are identified by name, e.g. `"priya"`.

Errors are `{ "detail": "..." }`: 404 for an unknown book, 409 when the book's current state
doesn't allow the action (checking out a book someone has, returning one that's on the
shelf), 422 for a bad request body.
