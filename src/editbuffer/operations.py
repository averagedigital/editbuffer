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
    "rollback",
]


@dataclass(frozen=True, slots=True)
class EditOperation:
    kind: OperationType
    target: Selection | None = None
    text: str = ""
    version: int | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EditOperation:
        kind = value.get("op")
        if kind not in {
            "append",
            "replace",
            "insert_before",
            "insert_after",
            "delete",
            "rollback",
        }:
            raise InvalidOperationError(f"unknown operation: {kind!r}")

        if kind == "rollback":
            version = value.get("version")
            if not isinstance(version, int):
                raise InvalidOperationError("'rollback' requires integer 'version'")
            return cls(kind, version=version)

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

    def as_dict(self) -> dict[str, Any]:
        if self.kind == "rollback":
            return {"op": "rollback", "version": self.version}
        result: dict[str, Any] = {"op": self.kind}
        if self.kind != "delete":
            result["text"] = self.text
        if self.target is not None:
            result["target"] = self.target.as_dict()
        return result
