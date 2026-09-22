"""Pure unit tests for notepad."""

from unittest.mock import MagicMock

import pytest

from app.features.notepad.services import NotepadService

pytestmark = pytest.mark.unit


def test_get_all_by_user_delegates_to_repository():
    service = NotepadService()
    service.repository = MagicMock()
    service.repository.get_all_by_user.return_value = ["note"]

    assert service.get_all_by_user(7) == ["note"]
    service.repository.get_all_by_user.assert_called_once_with(7)
