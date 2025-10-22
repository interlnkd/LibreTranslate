from flask import Blueprint

translations_blueprint = Blueprint("translations", __name__, url_prefix="/translations", template_folder="templates")

from . import tasks  # noqa