"""HTTP API for the office bookshelf. Run: uv run uvicorn app.main:app --reload"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from .library import Book, Conflict, Library, NotFound
from .schemas import BookList, BookOut, CheckoutRequest, NewBook

SEED = Path(__file__).resolve().parent.parent / "data" / "books.json"


def _out(book: Book) -> BookOut:
    return BookOut(**asdict(book))


def create_app(books: list[dict] | None = None) -> FastAPI:
    """An app with its own library, starting with ``books`` (empty if None)."""
    app = FastAPI(title="shelf")
    library = Library(books)
    app.state.library = library

    @app.exception_handler(NotFound)
    async def not_found(_: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_404_NOT_FOUND)

    @app.exception_handler(Conflict)
    async def conflict(_: Request, exc: Conflict) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_409_CONFLICT)

    @app.get("/books")
    def list_books() -> BookList:
        return BookList(books=[_out(b) for b in library.all()])

    @app.post("/books", status_code=status.HTTP_201_CREATED)
    def add_book(body: NewBook) -> BookOut:
        return _out(library.add(body.title, body.author))

    @app.get("/books/{book_id}")
    def get_book(book_id: int) -> BookOut:
        return _out(library.get(book_id))

    @app.post("/books/{book_id}/checkout")
    def checkout(book_id: int, body: CheckoutRequest) -> BookOut:
        return _out(library.checkout(book_id, body.member))

    @app.post("/books/{book_id}/return")
    def return_book(book_id: int) -> BookOut:
        return _out(library.return_book(book_id))

    @app.get("/members/{member}/books")
    def member_books(member: str) -> BookList:
        return BookList(books=[_out(b) for b in library.borrowed_by(member)])

    return app


def _seed() -> list[dict]:
    return json.loads(SEED.read_text()) if SEED.is_file() else []


app = create_app(_seed())
