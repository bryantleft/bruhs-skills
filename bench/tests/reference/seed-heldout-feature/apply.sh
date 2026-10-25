#!/usr/bin/env bash
# Reference solution: a hold line per book in Library, hand-off on return, three routes,
# README rows and tests. Runs in the workspace; $REFERENCE_DIR is this dir.
set -euo pipefail
cp -R "$REFERENCE_DIR/files/." .
python3 - <<'PY'
from pathlib import Path

lib = Path("app/library.py")
s = lib.read_text()
s = s.replace(
    "        self._books: dict[int, Book] = {}\n",
    "        self._books: dict[int, Book] = {}\n        self._holds: dict[int, list[str]] = {}\n")
s = s.replace(
    "        book.checked_out_by = None\n        return book\n",
    "        line = self._holds.get(book_id, [])\n"
    "        # straight to the first in line, else back on the shelf\n"
    "        book.checked_out_by = line.pop(0) if line else None\n"
    "        return book\n")
s += '''
    def holds(self, book_id: int) -> list[str]:
        self.get(book_id)
        return list(self._holds.get(book_id, []))

    def place_hold(self, book_id: int, member: str) -> list[str]:
        book = self.get(book_id)
        line = self._holds.setdefault(book_id, [])
        if book.checked_out_by is None:
            raise Conflict("book is on the shelf: check it out instead")
        if book.checked_out_by == member:
            raise Conflict(f"{member} already has this book")
        if member in line:
            raise Conflict(f"{member} is already in line")
        line.append(member)
        return list(line)

    def cancel_hold(self, book_id: int, member: str) -> list[str]:
        self.get(book_id)
        line = self._holds.get(book_id, [])
        if member not in line:
            raise NotFound(f"{member} has no hold on book {book_id}")
        line.remove(member)
        return list(line)
'''
lib.write_text(s)

main = Path("app/main.py")
s = main.read_text()
s = s.replace("from .schemas import BookList, BookOut, CheckoutRequest, NewBook",
              "from .schemas import BookList, BookOut, CheckoutRequest, HoldLine, NewBook")
s = s.replace('''    @app.get("/members/{member}/books")''', '''    @app.get("/books/{book_id}/holds")
    def holds(book_id: int) -> HoldLine:
        return HoldLine(holds=library.holds(book_id))

    @app.post("/books/{book_id}/holds", status_code=status.HTTP_201_CREATED)
    def place_hold(book_id: int, body: CheckoutRequest) -> HoldLine:
        return HoldLine(holds=library.place_hold(book_id, body.member))

    @app.delete("/books/{book_id}/holds/{member}")
    def cancel_hold(book_id: int, member: str) -> HoldLine:
        return HoldLine(holds=library.cancel_hold(book_id, member))

    @app.get("/members/{member}/books")''')
main.write_text(s)

schemas = Path("app/schemas.py")
schemas.write_text(schemas.read_text() + '''

class HoldLine(BaseModel):
    holds: list[str]
''')

readme = Path("README.md")
s = readme.read_text()
s = s.replace('''| GET | `/members/{member}/books` |''', '''| GET | `/books/{id}/holds` | | `{ "holds": [member] }`, first in line first |
| POST | `/books/{id}/holds` | `{ "member" }` | the line (201); only for a checked-out book |
| DELETE | `/books/{id}/holds/{member}` | | the line without that member |
| GET | `/members/{member}/books` |''')
s = s.replace("shelf), 422 for a bad request body.",
              "shelf, holding a book that's on the shelf or that you have, getting in line twice),\n"
              "422 for a bad request body. Returning a book with holds checks it out to the first\n"
              "member in line.")
readme.write_text(s)
PY
grep -q "def place_hold" app/library.py
grep -q '"/books/{book_id}/holds"' app/main.py
