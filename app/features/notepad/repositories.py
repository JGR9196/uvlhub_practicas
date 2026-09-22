from splent_framework.repositories.BaseRepository import BaseRepository

from app.features.notepad.models import Notepad


class NotepadRepository(BaseRepository):
    def __init__(self):
        super().__init__(Notepad)

    def get_all_by_user(self, user_id):
        return self.get_by_column("user_id", user_id)
