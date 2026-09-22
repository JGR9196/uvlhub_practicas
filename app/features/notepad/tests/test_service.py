"""Notepad service with a real database."""

import pytest
from werkzeug.exceptions import NotFound

from app.features.auth.repositories import UserRepository
from app.features.notepad.services import NotepadService

pytestmark = pytest.mark.service


def test_service_crud_only_lists_owner_notes(test_app, test_client):
    with test_app.app_context():
        owner = UserRepository().create(email="note-owner@example.com", password="secret")
        other = UserRepository().create(email="note-other@example.com", password="secret")
        service = NotepadService()
        assert service.get_all_by_user(owner.id) == []
        mine = service.create(title="Mine", body="Body", user_id=owner.id)
        service.create(title="Theirs", body="Private", user_id=other.id)
        assert [n.id for n in service.get_all_by_user(owner.id)] == [mine.id]
        note_id = mine.id
        service.update(note_id, title="Updated", body="Changed")
        assert service.get_or_404(note_id).title == "Updated"
        assert service.get_by_id(note_id).body == "Changed"
        assert service.delete(note_id)
        assert service.get_all_by_user(owner.id) == []


def test_missing_note_raises_not_found(test_app, test_client):
    with test_app.app_context():
        with pytest.raises(NotFound):
            NotepadService().get_or_404(999999)
