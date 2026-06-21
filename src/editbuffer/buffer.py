from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .errors import InvalidOperationError
from .history import EditHistory, EditRecord
from .operations import EditOperation
from .resolver import ResolvedSelection, SelectionResolver
from .selection import Selection

Validator = Callable[[str], None]


class EditBuffer:
    def __init__(
        self,
        content: str = "",
        *,
        validators: tuple[Validator, ...] = (),
    ) -> None:
        self._content = content
        self._version = 0
        self._committed = False
        self._validators = validators
        self._resolver = SelectionResolver()
        self._snapshots = {0: content}
        self.history = EditHistory()

    @property
    def version(self) -> int:
        return self._version

    @property
    def committed(self) -> bool:
        return self._committed

    @property
    def versions(self) -> tuple[int, ...]:
        return tuple(self._snapshots)

    def view(self) -> str:
        return self._content

    def append(self, text: str) -> EditRecord:
        return self._apply(EditOperation("append", text=text))

    def replace(
        self,
        target: Selection | Mapping[str, Any],
        text: str,
    ) -> EditRecord:
        return self._apply(EditOperation("replace", self._selection(target), text))

    def insert_before(
        self,
        target: Selection | Mapping[str, Any],
        text: str,
    ) -> EditRecord:
        return self._apply(
            EditOperation("insert_before", self._selection(target), text)
        )

    def insert_after(
        self,
        target: Selection | Mapping[str, Any],
        text: str,
    ) -> EditRecord:
        return self._apply(
            EditOperation("insert_after", self._selection(target), text)
        )

    def delete(self, target: Selection | Mapping[str, Any]) -> EditRecord:
        return self._apply(EditOperation("delete", self._selection(target)))

    def apply(
        self,
        operation: Mapping[str, Any] | EditOperation,
    ) -> EditRecord:
        return self._apply(
            operation
            if isinstance(operation, EditOperation)
            else EditOperation.from_dict(operation)
        )

    def commit(self) -> str:
        self._ensure_open()
        self._committed = True
        return self._content

    def rollback(self, version: int) -> EditRecord:
        return self._apply(EditOperation("rollback", version=version))

    def _apply(self, operation: EditOperation) -> EditRecord:
        self._ensure_open()
        if operation.kind == "rollback":
            return self._rollback(operation)
        resolved = self._resolve(operation)
        before = self._content[resolved.start : resolved.end]
        after = _replacement(operation, before)
        candidate = (
            self._content[: resolved.start]
            + after
            + self._content[resolved.end :]
        )
        for validator in self._validators:
            validator(candidate)

        version_before = self._version
        self._content = candidate
        self._version += 1
        self._snapshots[self._version] = candidate
        record = EditRecord(
            operation=operation,
            start=resolved.start,
            end=resolved.end,
            before=before,
            after=after,
            version_before=version_before,
            version_after=self._version,
            confidence=resolved.confidence,
        )
        self.history.append(record)
        return record

    def _rollback(self, operation: EditOperation) -> EditRecord:
        if operation.version not in self._snapshots:
            raise InvalidOperationError(f"unknown version: {operation.version}")
        candidate = self._snapshots[operation.version]
        for validator in self._validators:
            validator(candidate)
        before = self._content
        version_before = self._version
        self._content = candidate
        self._version += 1
        self._snapshots[self._version] = candidate
        record = EditRecord(
            operation=operation,
            start=0,
            end=len(before),
            before=before,
            after=candidate,
            version_before=version_before,
            version_after=self._version,
        )
        self.history.append(record)
        return record

    def _resolve(self, operation: EditOperation) -> ResolvedSelection:
        if operation.kind == "append":
            end = len(self._content)
            return ResolvedSelection(end, end)
        if operation.target is None:
            raise InvalidOperationError(f"{operation.kind} requires a target")
        return self._resolver.resolve(
            self._content,
            operation.target,
            version=self._version,
        )

    def _selection(self, value: Selection | Mapping[str, Any]) -> Selection:
        return value if isinstance(value, Selection) else Selection.from_dict(value)

    def _ensure_open(self) -> None:
        if self._committed:
            raise InvalidOperationError("buffer is already committed")


def _replacement(operation: EditOperation, before: str) -> str:
    if operation.kind == "append" or operation.kind == "replace":
        return operation.text
    if operation.kind == "insert_before":
        return operation.text + before
    if operation.kind == "insert_after":
        return before + operation.text
    if operation.kind == "delete":
        return ""
    raise InvalidOperationError(f"unknown operation: {operation.kind!r}")
