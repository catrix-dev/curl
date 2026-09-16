import copy
import json
import os
import sqlite3
from threading import RLock
from typing import Any, Optional, Union


GuildId = Union[int, str]


class JsonDatabaseStore:
    """使用 SQLite 保存原本的 JSON 文档数据。"""

    def __init__(self, base_dir: str = "data", global_namespace: str = "global"):
        self.base_dir = base_dir
        self.global_namespace = global_namespace
        self._locks: dict[str, RLock] = {}
        os.makedirs(self.base_dir, exist_ok=True)
        self.ensure_global_database()

    def get_guild_database_path(self, guild_id: GuildId) -> str:
        return os.path.join(self.base_dir, str(guild_id), "database.db")

    def get_global_database_path(self) -> str:
        return os.path.join(self.base_dir, self.global_namespace, "database.db")

    def ensure_guild_database(self, guild_id: GuildId) -> str:
        db_path = self.get_guild_database_path(guild_id)
        self._initialize_database(db_path)
        return db_path

    def ensure_global_database(self) -> str:
        db_path = self.get_global_database_path()
        self._initialize_database(db_path)
        return db_path

    def load_guild_data(
        self,
        guild_id: GuildId,
        key: str,
        default: Optional[Any] = None,
        legacy_filename: Optional[str] = None,
    ) -> Any:
        db_path = self.ensure_guild_database(guild_id)
        legacy_path = os.path.join(
            self.base_dir,
            str(guild_id),
            legacy_filename or f"{key}.json",
        )
        return self._load_document(db_path, key, default, legacy_path)

    def save_guild_data(self, guild_id: GuildId, key: str, value: Any) -> str:
        db_path = self.ensure_guild_database(guild_id)
        self._save_document(db_path, key, value)
        return db_path

    def has_guild_data(
        self,
        guild_id: GuildId,
        key: str,
        legacy_filename: Optional[str] = None,
    ) -> bool:
        db_path = self.ensure_guild_database(guild_id)
        legacy_path = os.path.join(
            self.base_dir,
            str(guild_id),
            legacy_filename or f"{key}.json",
        )
        return self._document_exists(db_path, key, legacy_path)

    def delete_guild_data(self, guild_id: GuildId, key: str) -> None:
        db_path = self.ensure_guild_database(guild_id)
        self._delete_document(db_path, key)

    def load_global_data(
        self,
        key: str,
        default: Optional[Any] = None,
        legacy_filename: Optional[str] = None,
    ) -> Any:
        db_path = self.ensure_global_database()
        legacy_path = os.path.join(self.base_dir, legacy_filename or f"{key}.json")
        return self._load_document(db_path, key, default, legacy_path)

    def save_global_data(self, key: str, value: Any) -> str:
        db_path = self.ensure_global_database()
        self._save_document(db_path, key, value)
        return db_path

    def has_global_data(self, key: str, legacy_filename: Optional[str] = None) -> bool:
        db_path = self.ensure_global_database()
        legacy_path = os.path.join(self.base_dir, legacy_filename or f"{key}.json")
        return self._document_exists(db_path, key, legacy_path)

    def _get_lock(self, db_path: str) -> RLock:
        lock = self._locks.get(db_path)
        if lock is None:
            lock = RLock()
            self._locks[db_path] = lock
        return lock

    def _initialize_database(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        lock = self._get_lock(db_path)
        with lock:
            with sqlite3.connect(db_path) as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS documents (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.commit()

    def _load_document(
        self,
        db_path: str,
        key: str,
        default: Optional[Any],
        legacy_path: Optional[str],
    ) -> Any:
        lock = self._get_lock(db_path)
        with lock:
            with sqlite3.connect(db_path) as connection:
                cursor = connection.execute(
                    "SELECT value FROM documents WHERE key = ?",
                    (key,),
                )
                row = cursor.fetchone()

        if row is not None:
            return json.loads(row[0])

        if legacy_path and os.path.exists(legacy_path):
            with open(legacy_path, "r", encoding="utf-8") as legacy_file:
                legacy_data = json.load(legacy_file)
            self._save_document(db_path, key, legacy_data)
            return legacy_data

        return self._clone_default(default)

    def _save_document(self, db_path: str, key: str, value: Any) -> None:
        serialized_value = json.dumps(value, ensure_ascii=False)
        lock = self._get_lock(db_path)
        with lock:
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    """
                    INSERT INTO documents (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (key, serialized_value),
                )
                connection.commit()

    def _document_exists(self, db_path: str, key: str, legacy_path: Optional[str]) -> bool:
        lock = self._get_lock(db_path)
        with lock:
            with sqlite3.connect(db_path) as connection:
                cursor = connection.execute(
                    "SELECT 1 FROM documents WHERE key = ? LIMIT 1",
                    (key,),
                )
                row = cursor.fetchone()

        if row is not None:
            return True

        return bool(legacy_path and os.path.exists(legacy_path))

    def _delete_document(self, db_path: str, key: str) -> None:
        lock = self._get_lock(db_path)
        with lock:
            with sqlite3.connect(db_path) as connection:
                connection.execute("DELETE FROM documents WHERE key = ?", (key,))
                connection.commit()

    @staticmethod
    def _clone_default(default: Optional[Any]) -> Any:
        if default is None:
            return {}
        return copy.deepcopy(default)