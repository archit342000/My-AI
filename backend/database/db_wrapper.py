import sqlite3
import logging
import os
from .db_layer import make_connection, DB_PATH
from .wrapper.base import BaseMixin, _log_db_wrapper_op
from .wrapper.chat_ops import ChatOpsMixin
from .wrapper.message_ops import MessageOpsMixin
from .wrapper.file_system_ops import FileSystemOpsMixin
from .wrapper.artifact_ops import ArtifactOpsMixin
from .wrapper.history_ops import HistoryOpsMixin
from .wrapper.preference_ops import PreferenceOpsMixin
from .wrapper.callback_ops import CallbackOpsMixin
from .wrapper.task_ops import TaskOpsMixin
from .wrapper.persona_ops import PersonaOperations
from .wrapper.skill_ops import SkillOpsMixin
from .wrapper.settings_ops import SettingsOpsMixin
from .wrapper.code_execution_ops import CodeExecutionOpsMixin
from .wrapper.clipboard_ops import ClipboardOpsMixin
from .wrapper.user_ops import UserOpsMixin

logger = logging.getLogger(__name__)

class DatabaseWrapper(
    ChatOpsMixin,
    MessageOpsMixin,
    FileSystemOpsMixin,
    ArtifactOpsMixin,
    HistoryOpsMixin,
    PreferenceOpsMixin,
    CallbackOpsMixin,
    TaskOpsMixin,
    PersonaOperations,
    SkillOpsMixin,
    SettingsOpsMixin,
    CodeExecutionOpsMixin,
    ClipboardOpsMixin,
    UserOpsMixin,
    BaseMixin
):

    """
    Unified database wrapper modularized into specialized mixins.
    Provides a high-level Cache-Aside interface for all DB operations.
    """

    def __init__(self):
        # Initialization is handled by mixins where necessary
        pass

# Standard singleton instance for the application
db = DatabaseWrapper()

# Export infrastructure components for backward compatibility
from backend.config import DATA_DIR
DB_PATH = os.path.join(DATA_DIR, "chats.db")
