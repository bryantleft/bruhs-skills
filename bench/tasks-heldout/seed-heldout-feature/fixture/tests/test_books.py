def test_lists_books(client):
    books = client.get("/books").json()["books"]
    assert [b["title"] for b in books] == ["Dune", "Piranesi"]
    assert books[1]["checked_out_by"] == "ana"


def test_add_book(client):
    res = client.post("/books", json={"title": "Kindred", "author": "Octavia E. Butler"})
    assert res.status_code == 201
    book = res.json()
    assert book["checked_out_by"] is None
    assert client.get(f"/books/{book['id']}").json()["title"] == "Kindred"


def test_add_book_needs_title_and_author(client):
    assert client.post("/books", json={"title": "Untitled"}).status_code == 422
    assert client.post("/books", json={"title": "", "author": "x"}).status_code == 422


def test_unknown_book_is_404(client):
    assert client.get("/books/99").status_code == 404
    assert client.post("/books/99/checkout", json={"member": "ben"}).status_code == 404


def test_checkout_and_return(client):
    res = client.post("/books/1/checkout", json={"member": "ben"})
    assert res.status_code == 200
    assert res.json()["checked_out_by"] == "ben"
    res = client.post("/books/1/return")
    assert res.status_code == 200
    assert res.json()["checked_out_by"] is None


def test_checkout_of_a_checked_out_book_is_409(client):
    res = client.post("/books/2/checkout", json={"member": "ben"})
    assert res.status_code == 409
    assert "ana" in res.json()["detail"]


def test_returning_a_book_on_the_shelf_is_409(client):
    assert client.post("/books/1/return").status_code == 409


def test_checkout_needs_a_member(client):
    assert client.post("/books/1/checkout", json={}).status_code == 422
    assert client.post("/books/1/checkout", json={"member": ""}).status_code == 422


def test_member_books(client):
    client.post("/books/1/checkout", json={"member": "ana"})
    books = client.get("/members/ana/books").json()["books"]
    assert [b["title"] for b in books] == ["Dune", "Piranesi"]
    assert client.get("/members/ben/books").json()["books"] == []
