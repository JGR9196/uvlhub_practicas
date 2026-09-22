"""Notepad persistence and database constraints."""

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.features.auth.repositories import UserRepository
from app.features.notepad.repositories import NotepadRepository

pytestmark = pytest.mark.repository


def test_repository_crud_and_owner_relationship(test_app, test_client):
    with test_app.app_context():
        owner = UserRepository().create(email="notepad-repo@example.com", password="secret")
        repo = NotepadRepository()
        note = repo.create(title="Title", body="Body", user_id=owner.id)
        note_id = note.id
        db.session.expire_all()
        saved = repo.get_by_id(note_id)
        assert saved.title == "Title"
        assert saved.body == "Body"
        assert saved.user == owner
        assert saved in owner.notepads
        assert owner.email in repr(saved)

        repo.update(note_id, title="Edited", body="Updated body")
        db.session.expire_all()
        assert repo.get_by_id(note_id).title == "Edited"
        assert repo.get_by_id(note_id).body == "Updated body"
        assert repo.get_by_id(note_id).user_id == owner.id
        assert repo.delete(note_id) is True
        assert repo.get_by_id(note_id) is None
        assert repo.delete(note_id) is False


def test_repository_filters_by_owner_and_allows_multiple_notes(test_app, test_client):
    with test_app.app_context():
        users = [UserRepository().create(email=f"notepad-{i}@example.com", password="secret") for i in range(3)]
        repo = NotepadRepository()
        for title in ("First", "Second"):
            repo.create(title=title, body="Mine", user_id=users[0].id)
        repo.create(title="Private", body="Theirs", user_id=users[1].id)
        assert {n.title for n in repo.get_all_by_user(users[0].id)} == {"First", "Second"}
        assert repo.get_all_by_user(users[2].id) == []


@pytest.mark.parametrize("field", ["title", "body", "user_id"])
def test_required_columns_reject_null(test_app, test_client, field):
    with test_app.app_context():
        user = UserRepository().create(email="notepad-null@example.com", password="secret")
        data = dict(title="Title", body="Body", user_id=user.id)
        data[field] = None
        with pytest.raises(IntegrityError):
            NotepadRepository().create(**data)
        db.session.rollback()


def test_foreign_key_rejects_unknown_user(test_app, test_client):
    with test_app.app_context():
        with pytest.raises(IntegrityError):
            NotepadRepository().create(title="Title", body="Body", user_id=999999)
        db.session.rollback()
