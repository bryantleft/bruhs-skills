"""The library's state: books and who has them. In memory; one instance per app."""

from __future__ import annotations

from dataclasses import dataclass


class NotFound(Exception):
    """No such book (or other thing the request names)."""


class Conflict(Exception):
    """The book's current state doesn't allow the action."""


@dataclass
class Book:
    id: int
    title: str
    author: str
    checked_out_by: str | None = None


class Library:
    def __init__(self, books: list[dict] | None = None) -> None:
        self._books: dict[int, Book] = {}
        self._next_id = 1
        for b in books or []:
            self.add(b["title"], b["author"], checked_out_by=b.get("checked_out_by"))

    def add(self, title: str, author: str, checked_out_by: str | None = None) -> Book:
        book = Book(self._next_id, title, author, checked_out_by)
        self._books[book.id] = book
        self._next_id += 1
        return book

    def all(self) -> list[Book]:
        return list(self._books.values())

    def get(self, book_id: int) -> Book:
        try:
            return self._books[book_id]
        except KeyError:
            raise NotFound(f"no book with id {book_id}") from None

    def checkout(self, book_id: int, member: str) -> Book:
        book = self.get(book_id)
        if book.checked_out_by is not None:
            raise Conflict(f"already checked out by {book.checked_out_by}")
        book.checked_out_by = member
        return book

    def return_book(self, book_id: int) -> Book:
        book = self.get(book_id)
        if book.checked_out_by is None:
            raise Conflict("book isn't checked out")
        book.checked_out_by = None
        return book

    def borrowed_by(self, member: str) -> list[Book]:
        return [b for b in self._books.values() if b.checked_out_by == member]
