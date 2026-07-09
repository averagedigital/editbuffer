from __future__ import annotations

import json
import os
import re
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
COMMAND_KEYS = ("command", "command_line", "cmd")
SHELL_TOOL_NAMES = {"bash", "exec_command", "run_shell_command", "shell", "terminal"}
CONTEXT_COLUMNS = {
    "session_id": "TEXT",
    "cwd": "TEXT",
    "provider": "TEXT",
    "tool_kind": "TEXT",
    "parent_call_id": "TEXT",
}
TOOL_CALL_COLUMNS = (
    "call_id, timestamp, tool_name, arguments_json, result_json, result_summary, "
    "status, error, content, command, session_id, cwd, provider, tool_kind, parent_call_id"
)

_SECRET_NAME = (
    r"(?:api[_-]?(?:key|token)|access[_-]?token|token|secret|password|passwd|cookie)"
)
_AUTH_VALUE = re.compile(
    r"(authorization\s*(?:=|:)\s*(?:(?:basic|bearer)\s+)?)([^\s'\";&|]+)",
    re.IGNORECASE,
)
_QUOTED_SECRET = re.compile(
    rf"((?<![\w-])(?:--?)?{_SECRET_NAME}\s*(?:=|:|\s)\s*)(['\"])(.*?)\2",
    re.IGNORECASE,
)
_UNQUOTED_SECRET = re.compile(
    rf"((?<![\w-])(?:--?)?{_SECRET_NAME}\s*(?:=|:|\s)\s*)([^\s'\";&|]+)",
    re.IGNORECASE,
)


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
        session_id: str | None = None,
        cwd: str | Path | None = None,
        provider: str | None = None,
        tool_kind: str | None = None,
        parent_call_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> str:
        self.cleanup()
        identifier = call_id or f"call-{uuid4().hex}"
        when = timestamp or datetime.now(UTC)
        resolved_kind = tool_kind or ("shell" if _is_shell_tool(tool_name) else None)
        is_shell = resolved_kind == "shell"
        source_command = command or _command_from(arguments or {}) if is_shell else None
        stored_command = (
            _redact_command(source_command) if source_command is not None else None
        )
        stored_content = (
            _redact_command(content) if is_shell and content is not None else content
        )
        if stored_content is None:
            stored_content = stored_command
        redacted_arguments = _redact(arguments or {})
        redacted_result = _redact(result)
        with self._connect() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO tool_calls (
                    call_id, timestamp, tool_name, arguments_json, result_json,
                    result_summary, status, error, content, command, session_id,
                    cwd, provider, tool_kind, parent_call_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    stored_content,
                    stored_command,
                    session_id,
                    str(cwd) if cwd is not None else None,
                    provider,
                    resolved_kind,
                    parent_call_id,
                ),
            )
        return identifier

    def last_failed(
        self,
        *,
        session_id: str | None = None,
        cwd: str | Path | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        self.cleanup()
        clauses = [
            "status = 'failed'",
            "parent_call_id IS NULL",
            _shell_clause(),
        ]
        params = _add_scope(clauses, session_id=session_id, cwd=cwd, provider=provider)
        with self._connect() as db:
            row = db.execute(
                f"""
                SELECT {TOOL_CALL_COLUMNS}
                FROM tool_calls
                WHERE {" AND ".join(clauses)}
                ORDER BY timestamp DESC, rowid DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
        if row is None:
            raise KeyError("no failed tool call")
        return _row(row)

    def list_tool_calls(
        self,
        limit: int | None = None,
        *,
        session_id: str | None = None,
        cwd: str | Path | None = None,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        self.cleanup()
        row_limit = self.default_limit if limit is None else limit
        clauses: list[str] = []
        params = _add_scope(clauses, session_id=session_id, cwd=cwd, provider=provider)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT {TOOL_CALL_COLUMNS}
                FROM tool_calls
                {where}
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ?
                """,
                (*params, row_limit),
            ).fetchall()
        return [_row(row) for row in rows]

    def get_tool_call(
        self,
        call_id: str,
        *,
        session_id: str | None = None,
        cwd: str | Path | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        self.cleanup()
        clauses = ["call_id = ?"]
        params: list[Any] = [call_id]
        params.extend(
            _add_scope(clauses, session_id=session_id, cwd=cwd, provider=provider)
        )
        with self._connect() as db:
            row = db.execute(
                f"""
                SELECT {TOOL_CALL_COLUMNS}
                FROM tool_calls
                WHERE {" AND ".join(clauses)}
                """,
                params,
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown tool call: {call_id}")
        return _row(row)

    def command_history(
        self,
        limit: int | None = 5,
        *,
        session_id: str | None = None,
        cwd: str | Path | None = None,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        row_limit = 5 if limit is None else limit
        if not 1 <= row_limit <= 5:
            raise ValueError("history limit must be between 1 and 5")
        clauses = ["command IS NOT NULL", "command != ''", _shell_clause()]
        params = _add_scope(clauses, session_id=session_id, cwd=cwd, provider=provider)
        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT call_id, timestamp, tool_name, result_summary, status, error, command
                FROM tool_calls
                WHERE {" AND ".join(clauses)}
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ?
                """,
                (*params, row_limit),
            ).fetchall()
        return [
            {
                "command_id": row[0],
                "call_id": row[0],
                "created_at": row[1],
                "tool_name": row[2],
                "result_summary": row[3],
                "status": row[4],
                "error": row[5],
                "command": row[6],
            }
            for row in rows
        ]

    def get_command(
        self,
        command_id: str,
        *,
        session_id: str | None = None,
        cwd: str | Path | None = None,
        provider: str | None = None,
    ) -> str:
        clauses = [
            "call_id = ?",
            "command IS NOT NULL",
            "command != ''",
            _shell_clause(),
        ]
        params: list[Any] = [command_id]
        params.extend(
            _add_scope(clauses, session_id=session_id, cwd=cwd, provider=provider)
        )
        with self._connect() as db:
            row = db.execute(
                f"""
                SELECT command
                FROM tool_calls
                WHERE {" AND ".join(clauses)}
                """,
                params,
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown command: {command_id}")
        return str(row[0])

    def cleanup(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=self.retention_days)
        with self._connect() as db:
            db.execute(
                "DELETE FROM tool_calls WHERE timestamp < ?", (cutoff.isoformat(),)
            )

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
                    command TEXT,
                    session_id TEXT,
                    cwd TEXT,
                    provider TEXT,
                    tool_kind TEXT,
                    parent_call_id TEXT
                )
                """
            )
            existing_columns = {
                row[1] for row in db.execute("PRAGMA table_info(tool_calls)").fetchall()
            }
            for name, declaration in CONTEXT_COLUMNS.items():
                if name not in existing_columns:
                    db.execute(
                        f"ALTER TABLE tool_calls ADD COLUMN {name} {declaration}"
                    )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_tool_calls_timestamp ON tool_calls(timestamp)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_tool_calls_scope "
                "ON tool_calls(session_id, cwd, timestamp)"
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
            normalized_key = str(key).lower()
            if normalized_key in COMMAND_KEYS and isinstance(item, str):
                redacted[key] = _redact_command(item)
            elif any(secret in normalized_key for secret in SECRET_KEYS):
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


def _redact_command(command: str) -> str:
    redacted = _AUTH_VALUE.sub(r"\1[REDACTED]", command)
    redacted = _QUOTED_SECRET.sub(r"\1\2[REDACTED]\2", redacted)
    return _UNQUOTED_SECRET.sub(r"\1[REDACTED]", redacted)


def _command_from(value: dict[str, Any]) -> str | None:
    for key in COMMAND_KEYS:
        command = value.get(key)
        if isinstance(command, str) and command:
            return command
    return None


def _is_shell_tool(tool_name: str) -> bool:
    normalized = tool_name.lower().replace("-", "_")
    return normalized in SHELL_TOOL_NAMES or any(
        normalized.endswith(f"__{name}") for name in SHELL_TOOL_NAMES
    )


def _shell_clause() -> str:
    return "(tool_kind = 'shell' OR (tool_kind IS NULL AND command IS NOT NULL))"


def _add_scope(
    clauses: list[str],
    *,
    session_id: str | None,
    cwd: str | Path | None,
    provider: str | None,
) -> list[Any]:
    params: list[Any] = []
    for column, value in (
        ("session_id", session_id),
        ("cwd", str(cwd) if cwd is not None else None),
        ("provider", provider),
    ):
        if value is not None:
            clauses.append(f"{column} = ?")
            params.append(value)
    return params


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
        "session_id": row[10],
        "cwd": row[11],
        "provider": row[12],
        "tool_kind": row[13],
        "parent_call_id": row[14],
    }
