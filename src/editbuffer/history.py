from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from dataclasses import dataclass
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

from .operations import EditOperation


@dataclass(frozen=True, slots=True)
class EditRecord:
    operation: EditOperation
    start: int
    end: int
    before: str
    after: str
    version_before: int
    version_after: int
    confidence: float = 1.0


class EditHistory:
    def __init__(self) -> None:
        self._records: list[EditRecord] = []

    def append(self, record: EditRecord) -> None:
        self._records.append(record)

    def __len__(self) -> int:
        return len(self._records)

    def __getitem__(self, index: int) -> EditRecord:
        return self._records[index]

    def __iter__(self) -> Iterator[EditRecord]:
        return iter(self._records)


SECRET_KEYS = ("api_key", "token", "secret", "password", "authorization", "cookie")


class ToolHistoryStore:
    def __init__(
        self,
        path: str | Path | None = None,
        *,
        retention_days: int | None = None,
        default_limit: int | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else _default_history_path()
        self.retention_days = (
            retention_days
            if retention_days is not None
            else int(os.environ.get("EDITBUFFER_HISTORY_RETENTION_DAYS", "7"))
        )
        self.default_limit = (
            default_limit
            if default_limit is not None
            else int(os.environ.get("EDITBUFFER_HISTORY_LIMIT", "10"))
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.cleanup()

    def record_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        call_id: str | None = None,
        result: Any = None,
        status: str = "success",
        error: str | None = None,
        result_summary: str | None = None,
        content: str | None = None,
        command: str | None = None,
        timestamp: datetime | None = None,
    ) -> str:
        self.cleanup()
        identifier = call_id or f"call-{uuid4().hex}"
        when = timestamp or datetime.now(UTC)
        redacted_arguments = _redact(arguments or {})
        redacted_result = _redact(result)
        with self._connect() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO tool_calls (
                    call_id, timestamp, tool_name, arguments_json, result_json,
                    result_summary, status, error, content, command
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    when.isoformat(),
                    tool_name,
                    _json_dump(redacted_arguments),
                    _json_dump(redacted_result),
                    result_summary or _summary(redacted_result),
                    status,
                    error,
                    content,
                    command,
                ),
            )
        return identifier

    def last_failed(self) -> dict[str, Any]:
        self.cleanup()
        with self._connect() as db:
            row = db.execute(
                """
                SELECT call_id, timestamp, tool_name, arguments_json, result_json,
                       result_summary, status, error, content, command
                FROM tool_calls
                WHERE status = 'failed'
                ORDER BY timestamp DESC, rowid DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            raise KeyError("no failed tool call")
        return _row(row)

    def list_tool_calls(self, limit: int | None = None) -> list[dict[str, Any]]:
        self.cleanup()
        row_limit = self.default_limit if limit is None else limit
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT call_id, timestamp, tool_name, arguments_json, result_json,
                       result_summary, status, error, content, command
                FROM tool_calls
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ?
                """,
                (row_limit,),
            ).fetchall()
        return [_row(row) for row in rows]

    def get_tool_call(self, call_id: str) -> dict[str, Any]:
        self.cleanup()
        with self._connect() as db:
            row = db.execute(
                """
                SELECT call_id, timestamp, tool_name, arguments_json, result_json,
                       result_summary, status, error, content, command
                FROM tool_calls
                WHERE call_id = ?
                """,
                (call_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown tool call: {call_id}")
        return _row(row)

    def command_history(self, limit: int | None = None) -> list[dict[str, str]]:
        row_limit = self.default_limit if limit is None else limit
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT call_id, command
                FROM tool_calls
                WHERE command IS NOT NULL AND command != ''
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ?
                """,
                (row_limit,),
            ).fetchall()
        return [{"command_id": row[0], "command": row[1]} for row in rows]

    def get_command(self, command_id: str) -> str:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT command
                FROM tool_calls
                WHERE call_id = ? AND command IS NOT NULL AND command != ''
                """,
                (command_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown command: {command_id}")
        return str(row[0])

    def cleanup(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=self.retention_days)
        with self._connect() as db:
            db.execute("DELETE FROM tool_calls WHERE timestamp < ?", (cutoff.isoformat(),))

    def _init_db(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_calls (
                    call_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    result_json TEXT,
                    result_summary TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    content TEXT,
                    command TEXT
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_tool_calls_timestamp ON tool_calls(timestamp)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _default_history_path() -> Path:
    configured = os.environ.get("EDITBUFFER_HISTORY_DB")
    if configured:
        return Path(configured)
    return Path.home() / ".editbuffer" / "history.sqlite3"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if any(secret in str(key).lower() for secret in SECRET_KEYS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_load(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


def _summary(value: Any) -> str | None:
    if value is None:
        return None
    text = _json_dump(value)
    if text is None:
        return None
    return text[:500]


def _row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "call_id": row[0],
        "created_at": row[1],
        "timestamp": row[1],
        "tool_name": row[2],
        "arguments": _json_load(row[3]),
        "result": _json_load(row[4]),
        "result_summary": row[5],
        "status": row[6],
        "error": row[7],
        "content": row[8],
        "command": row[9],
    }
