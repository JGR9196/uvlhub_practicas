from flask import Flask
from splent_framework.blueprints.base_blueprint import BaseBlueprint
from splent_framework.nav.nav_registry import register_nav_item

notepad_bp = BaseBlueprint("notepad", __name__, template_folder="templates")


def init_feature(app: Flask) -> None:
    register_nav_item("notepad", "My notepads", "/notepad", order=40, icon="file-text")
