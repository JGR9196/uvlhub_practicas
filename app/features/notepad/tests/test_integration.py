"""HTTP CRUD, authorization, validation and CSRF regression tests."""

import pytest
from bs4 import BeautifulSoup

from app.features.auth.repositories import UserRepository
from app.features.notepad.repositories import NotepadRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def logged_in(test_client):
    response = test_client.post(
        "/signup/",
        data={"email": "notepad-http@example.com", "password": "secret", "name": "Ada", "surname": "Lovelace"},
    )
    assert response.status_code == 302
    return test_client


def create_note(client, title="My note", body="My body"):
    response = client.post("/notepad/create", data={"title": title, "body": body})
    assert response.status_code == 302
    with client.application.app_context():
        return NotepadRepository().get_by_column("title", title)[0].id


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/notepad"),
        ("get", "/notepad/create"),
        ("post", "/notepad/create"),
        ("get", "/notepad/1"),
        ("get", "/notepad/edit/1"),
        ("post", "/notepad/edit/1"),
        ("post", "/notepad/delete/1"),
    ],
)
def test_routes_require_login(test_client, method, path):
    response = getattr(test_client, method)(path)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_complete_crud(logged_in):
    assert "You have no notepads." in logged_in.get("/notepad").text
    assert logged_in.get("/notepad/create").status_code == 200
    note_id = create_note(logged_in)
    listing = logged_in.get("/notepad")
    assert "Notepad created successfully!" in listing.text
    assert "My note" in listing.text
    assert f"/notepad/{note_id}" in listing.text
    detail = logged_in.get(f"/notepad/{note_id}")
    assert detail.status_code == 200
    assert "My body" in detail.text
    edit = logged_in.get(f"/notepad/edit/{note_id}")
    assert edit.status_code == 200
    assert 'value="My note"' in edit.text
    assert "My body" in edit.text
    response = logged_in.post(
        f"/notepad/edit/{note_id}", data={"title": "Updated", "body": "Updated body"}, follow_redirects=True
    )
    assert "Notepad updated successfully!" in response.text
    assert "Updated body" in logged_in.get(f"/notepad/{note_id}").text
    response = logged_in.post(f"/notepad/delete/{note_id}", follow_redirects=True)
    assert "Notepad deleted successfully!" in response.text
    assert "You have no notepads." in response.text
    assert logged_in.get(f"/notepad/{note_id}").status_code == 404


@pytest.mark.parametrize(
    "title,body", [("", "Body"), ("   ", "Body"), ("Title", ""), ("Title", "  "), ("x" * 257, "Body")]
)
@pytest.mark.parametrize("edit", [False, True])
def test_invalid_forms_do_not_change_database(logged_in, title, body, edit):
    note_id = create_note(logged_in)
    path = f"/notepad/edit/{note_id}" if edit else "/notepad/create"
    response = logged_in.post(path, data={"title": title, "body": body})
    assert response.status_code == 200
    assert 'role="alert"' in response.text
    with logged_in.application.app_context():
        repo = NotepadRepository()
        assert repo.count() == 1
        note = repo.get_by_id(note_id)
        assert (note.title, note.body) == ("My note", "My body")


def test_maximum_title_length_is_accepted(logged_in):
    note_id = create_note(logged_in, title="x" * 256)
    assert logged_in.get(f"/notepad/{note_id}").status_code == 200


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/notepad/{id}"),
        ("get", "/notepad/edit/{id}"),
        ("post", "/notepad/edit/{id}"),
        ("post", "/notepad/delete/{id}"),
    ],
)
def test_other_users_notes_are_private(logged_in, method, path):
    with logged_in.application.app_context():
        other = UserRepository().create(email="private@example.com", password="secret")
        note = NotepadRepository().create(title="Private title", body="Private body", user_id=other.id)
        note_id = note.id
    assert "Private title" not in logged_in.get("/notepad").text
    response = getattr(logged_in, method)(path.format(id=note_id), data={"title": "Hacked", "body": "Hacked"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/notepad")
    listing = logged_in.get("/notepad")
    assert "not authorized" in listing.text
    assert "Private body" not in listing.text
    with logged_in.application.app_context():
        note = NotepadRepository().get_by_id(note_id)
        assert note.title == "Private title"
        assert note.body == "Private body"


def test_owner_is_taken_from_session_and_cannot_be_changed(logged_in):
    with logged_in.application.app_context():
        other = UserRepository().create(email="forged@example.com", password="secret")
        other_id = other.id
    response = logged_in.post("/notepad/create", data={"title": "Mine", "body": "Body", "user_id": other_id})
    assert response.status_code == 302
    with logged_in.application.app_context():
        note = NotepadRepository().get_by_column("title", "Mine")[0]
        note_id, owner_id = note.id, note.user_id
        assert owner_id != other_id
    logged_in.post(f"/notepad/edit/{note_id}", data={"title": "Edited", "body": "Body", "user_id": other_id})
    with logged_in.application.app_context():
        assert NotepadRepository().get_by_id(note_id).user_id == owner_id


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/notepad/999999"),
        ("get", "/notepad/edit/999999"),
        ("post", "/notepad/edit/999999"),
        ("post", "/notepad/delete/999999"),
    ],
)
def test_unknown_notes_return_404(logged_in, method, path):
    assert getattr(logged_in, method)(path).status_code == 404


def test_delete_is_post_only(logged_in):
    note_id = create_note(logged_in)
    assert logged_in.get(f"/notepad/delete/{note_id}").status_code == 405
    assert logged_in.get(f"/notepad/{note_id}").status_code == 200


def test_note_content_is_escaped(logged_in):
    payload = "<script>alert(1)</script>"
    note_id = create_note(logged_in, title=payload, body=payload)
    for path in ("/notepad", f"/notepad/{note_id}", f"/notepad/edit/{note_id}"):
        response = logged_in.get(path)
        assert payload not in response.text
        assert "&lt;script&gt;" in response.text


def csrf_token(response):
    return BeautifulSoup(response.text, "html.parser").find("input", {"name": "csrf_token"})["value"]


@pytest.mark.parametrize("token", [None, "invalid-token"])
@pytest.mark.parametrize("action", ["create", "edit", "delete"])
def test_mutations_reject_missing_or_invalid_csrf(logged_in, monkeypatch, token, action):
    note_id = create_note(logged_in)
    monkeypatch.setitem(logged_in.application.config, "WTF_CSRF_ENABLED", True)
    data = {"title": "Changed", "body": "Changed"}
    if token is not None:
        data["csrf_token"] = token
    path = "/notepad/create" if action == "create" else f"/notepad/{action}/{note_id}"
    response = logged_in.post(path, data=data)
    assert response.status_code == (400 if action == "delete" else 200)
    with logged_in.application.app_context():
        assert NotepadRepository().count() == 1
        assert NotepadRepository().get_by_id(note_id).title == "My note"


def test_crud_with_valid_csrf_tokens(logged_in, monkeypatch):
    monkeypatch.setitem(logged_in.application.config, "WTF_CSRF_ENABLED", True)
    token = csrf_token(logged_in.get("/notepad/create"))
    response = logged_in.post("/notepad/create", data={"title": "CSRF", "body": "Body", "csrf_token": token})
    assert response.status_code == 302
    with logged_in.application.app_context():
        note_id = NotepadRepository().get_by_column("title", "CSRF")[0].id
    token = csrf_token(logged_in.get(f"/notepad/edit/{note_id}"))
    response = logged_in.post(
        f"/notepad/edit/{note_id}", data={"title": "Updated", "body": "Body", "csrf_token": token}
    )
    assert response.status_code == 302
    token = csrf_token(logged_in.get("/notepad"))
    response = logged_in.post(f"/notepad/delete/{note_id}", data={"csrf_token": token})
    assert response.status_code == 302
    with logged_in.application.app_context():
        assert NotepadRepository().get_by_id(note_id) is None
