from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from threading import Lock

import structlog

from evalos.memory.models import MemoryState


class JsonMemoryStorage:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = Lock()
        self._logger = structlog.get_logger("evalos.memory.storage.json")

    def load_sync(self) -> MemoryState:
        with self._lock:
            if not self._path.exists():
                return MemoryState()
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
                return MemoryState.model_validate(payload)
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.warning("memory_load_failed", error=str(exc))
                return MemoryState()

    def save_sync(self, state: MemoryState) -> None:
        with self._lock:
            try:
                payload = state.model_dump()
                self._path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8"
                )
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.error("memory_save_failed", error=str(exc))

    async def load(self) -> MemoryState:
        return await asyncio.to_thread(self.load_sync)

    async def save(self, state: MemoryState) -> None:
        await asyncio.to_thread(self.save_sync, state)


class SQLiteMemoryStorage:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = Lock()
        self._logger = structlog.get_logger("evalos.memory.storage.sqlite")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path.as_posix(), check_same_thread=False)

    def _ensure_table(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS memory_state (id INTEGER PRIMARY KEY, payload TEXT)"
        )
        connection.commit()

    def load_sync(self) -> MemoryState:
        with self._lock:
            try:
                with self._connect() as connection:
                    self._ensure_table(connection)
                    row = connection.execute(
                        "SELECT payload FROM memory_state WHERE id = 1"
                    ).fetchone()
                    if not row:
                        return MemoryState()
                    payload = json.loads(row[0])
                    return MemoryState.model_validate(payload)
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.warning("memory_load_failed", error=str(exc))
                return MemoryState()

    def save_sync(self, state: MemoryState) -> None:
        with self._lock:
            try:
                payload = json.dumps(state.model_dump(), ensure_ascii=True)
                with self._connect() as connection:
                    self._ensure_table(connection)
                    connection.execute(
                        "INSERT OR REPLACE INTO memory_state (id, payload) VALUES (1, ?)",
                        (payload,),
                    )
                    connection.commit()
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.error("memory_save_failed", error=str(exc))

    async def load(self) -> MemoryState:
        return await asyncio.to_thread(self.load_sync)

    async def save(self, state: MemoryState) -> None:
        await asyncio.to_thread(self.save_sync, state)
