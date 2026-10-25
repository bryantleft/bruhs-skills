def test_hold_and_hand_off(client):
    assert client.post("/books/2/holds", json={"member": "ben"}).status_code == 201
    assert client.post("/books/2/holds", json={"member": "cat"}).status_code == 201
    assert client.get("/books/2/holds").json() == {"holds": ["ben", "cat"]}
    assert client.post("/books/2/return").json()["checked_out_by"] == "ben"
    assert client.get("/books/2/holds").json() == {"holds": ["cat"]}


def test_hold_conflicts(client):
    assert client.post("/books/1/holds", json={"member": "ben"}).status_code == 409
    assert client.post("/books/2/holds", json={"member": "ana"}).status_code == 409
    client.post("/books/2/holds", json={"member": "ben"})
    assert client.post("/books/2/holds", json={"member": "ben"}).status_code == 409


def test_cancel_hold(client):
    client.post("/books/2/holds", json={"member": "ben"})
    client.post("/books/2/holds", json={"member": "cat"})
    assert client.delete("/books/2/holds/ben").json() == {"holds": ["cat"]}
    assert client.delete("/books/2/holds/ben").status_code == 404
