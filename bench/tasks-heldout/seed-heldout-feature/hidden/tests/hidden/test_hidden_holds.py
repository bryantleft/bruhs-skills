"""Hidden tests for holds (a queue per checked-out book).

Only the API from the prompt and the README is used: create_app(), POST /books,
checkout/return, GET /books/{id}, GET /members/{m}/books, and the new
POST/GET /books/{id}/holds and DELETE /books/{id}/holds/{member}. Status codes follow the
README's conventions (404 unknown book, 409 state conflict, 422 bad body); a successful
hold or cancel may answer 200, 201 or 204, and its body isn't checked. Dropping a hold you
don't have may answer anything but a server error (the prompt doesn't settle it).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

OK = (200, 201, 204)


@pytest.fixture
def api() -> TestClient:
    return TestClient(create_app())


def add_book(api: TestClient, title: str = "Dune", *, borrower: str | None = None) -> int:
    res = api.post("/books", json={"title": title, "author": "Someone"})
    assert res.status_code == 201
    book_id = res.json()["id"]
    if borrower is not None:
        assert api.post(f"/books/{book_id}/checkout", json={"member": borrower}).status_code == 200
    return book_id


def hold(api: TestClient, book_id: int, member: str):
    return api.post(f"/books/{book_id}/holds", json={"member": member})


def line(api: TestClient, book_id: int) -> list[str]:
    res = api.get(f"/books/{book_id}/holds")
    assert res.status_code == 200
    return res.json()["holds"]


def holder(api: TestClient, book_id: int) -> str | None:
    return api.get(f"/books/{book_id}").json()["checked_out_by"]


# --------------------------------------------------------------------------- placing holds


def test_hold_on_a_checked_out_book(api):
    book = add_book(api, borrower="ana")
    assert hold(api, book, "sam").status_code in OK
    assert line(api, book) == ["sam"]


def test_line_is_in_the_order_holds_were_placed(api):
    book = add_book(api, borrower="ana")
    for member in ("sam", "priya", "dan"):
        assert hold(api, book, member).status_code in OK
    assert line(api, book) == ["sam", "priya", "dan"]


def test_book_without_holds_has_an_empty_line(api):
    assert line(api, add_book(api)) == []
    assert line(api, add_book(api, "Emma", borrower="ana")) == []


def test_hold_on_a_book_on_the_shelf_is_409(api):
    book = add_book(api)
    assert hold(api, book, "sam").status_code == 409
    assert line(api, book) == []
    assert holder(api, book) is None


def test_borrower_cannot_hold_their_own_book(api):
    book = add_book(api, borrower="ana")
    assert hold(api, book, "ana").status_code == 409
    assert line(api, book) == []


def test_cannot_get_in_line_twice(api):
    book = add_book(api, borrower="ana")
    assert hold(api, book, "sam").status_code in OK
    assert hold(api, book, "priya").status_code in OK
    assert hold(api, book, "sam").status_code == 409
    assert line(api, book) == ["sam", "priya"]


def test_hold_needs_a_member(api):
    book = add_book(api, borrower="ana")
    assert api.post(f"/books/{book}/holds", json={}).status_code == 422
    assert line(api, book) == []


def test_unknown_book_is_404(api):
    assert hold(api, 404, "sam").status_code == 404
    assert api.get("/books/404/holds").status_code == 404
    assert api.delete("/books/404/holds/sam").status_code == 404


def test_lines_are_per_book(api):
    a = add_book(api, "A", borrower="ana")
    b = add_book(api, "B", borrower="ana")
    hold(api, a, "sam")
    hold(api, b, "priya")
    assert line(api, a) == ["sam"]
    assert line(api, b) == ["priya"]


# --------------------------------------------------------------------------- returns


def test_return_goes_to_the_first_in_line(api):
    book = add_book(api, borrower="ana")
    hold(api, book, "sam")
    hold(api, book, "priya")
    assert api.post(f"/books/{book}/return").status_code == 200
    assert holder(api, book) == "sam"
    assert line(api, book) == ["priya"]


def test_book_works_down_the_line_then_back_to_the_shelf(api):
    book = add_book(api, borrower="ana")
    hold(api, book, "sam")
    hold(api, book, "priya")
    api.post(f"/books/{book}/return")
    api.post(f"/books/{book}/return")
    assert holder(api, book) == "priya"
    assert line(api, book) == []
    assert api.post(f"/books/{book}/return").status_code == 200
    assert holder(api, book) is None


def test_return_without_holds_puts_the_book_back(api):
    book = add_book(api, borrower="ana")
    assert api.post(f"/books/{book}/return").status_code == 200
    assert holder(api, book) is None
    assert api.post(f"/books/{book}/checkout", json={"member": "dan"}).status_code == 200


def test_next_in_line_shows_up_in_their_books(api):
    book = add_book(api, borrower="ana")
    hold(api, book, "sam")
    api.post(f"/books/{book}/return")
    assert [b["id"] for b in api.get("/members/sam/books").json()["books"]] == [book]
    assert api.get("/members/ana/books").json()["books"] == []


def test_previous_borrower_can_get_back_in_line(api):
    book = add_book(api, borrower="ana")
    hold(api, book, "sam")
    api.post(f"/books/{book}/return")
    assert hold(api, book, "ana").status_code in OK
    assert line(api, book) == ["ana"]


# --------------------------------------------------------------------------- leaving the line


def test_drop_out_of_line(api):
    book = add_book(api, borrower="ana")
    for member in ("sam", "priya", "dan"):
        hold(api, book, member)
    assert api.delete(f"/books/{book}/holds/priya").status_code in OK
    assert line(api, book) == ["sam", "dan"]


def test_dropped_member_is_skipped_on_return(api):
    book = add_book(api, borrower="ana")
    hold(api, book, "sam")
    hold(api, book, "priya")
    api.delete(f"/books/{book}/holds/sam")
    api.post(f"/books/{book}/return")
    assert holder(api, book) == "priya"
    assert line(api, book) == []


def test_dropping_a_hold_you_dont_have_changes_nothing(api):
    # 404, 409 or an idempotent 2xx are all defensible; only a server error isn't
    book = add_book(api, borrower="ana")
    hold(api, book, "sam")
    assert api.delete(f"/books/{book}/holds/priya").status_code < 500
    assert line(api, book) == ["sam"]


def test_can_get_back_in_line_after_dropping_out(api):
    book = add_book(api, borrower="ana")
    hold(api, book, "sam")
    hold(api, book, "priya")
    api.delete(f"/books/{book}/holds/sam")
    assert hold(api, book, "sam").status_code in OK
    assert line(api, book) == ["priya", "sam"]
