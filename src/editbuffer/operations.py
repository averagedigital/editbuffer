from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from .errors import InvalidOperationError
from .selection import Selection

OperationType = Literal[
    "append",
    "replace",
    "insert_before",
    "insert_after",
    "delete",
]


@dataclass(frozen=True, slots=True)
class EditOperation:
    kind: OperationType
    target: Selection | None = None
    text: str = ""

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EditOperation:
        kind = value.get("op")
        if kind not in {
            "append",
            "replace",
            "insert_before",
            "insert_after",
            "delete",
        }:
            raise InvalidOperationError(f"unknown operation: {kind!r}")

        if kind != "delete" and "text" not in value:
            raise InvalidOperationError(f"{kind!r} requires 'text'")
        text = value.get("text", "")
        if not isinstance(text, str):
            raise InvalidOperationError("'text' must be a string")

        if kind == "append":
            return cls(kind, text=text)

        target = value.get("target")
        if not isinstance(target, Mapping):
            raise InvalidOperationError("'target' must be a selection object")
        return cls(kind, target=Selection.from_dict(target), text=text)
