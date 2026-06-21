from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from .errors import InvalidOperationError

SelectionType = Literal["exact", "context", "range"]


@dataclass(frozen=True, slots=True)
class Selection:
    type: SelectionType
    text: str | None = None
    before: str = ""
    after: str = ""
    start: int | None = None
    end: int | None = None
    occurrence: int | None = None
    expected_version: int | None = None

    @classmethod
    def exact(cls, text: str, occurrence: int | None = None) -> Selection:
        return cls("exact", text=text, occurrence=occurrence)

    @classmethod
    def context(
        cls,
        *,
        before: str,
        text: str,
        after: str,
        occurrence: int | None = None,
    ) -> Selection:
        return cls(
            "context",
            text=text,
            before=before,
            after=after,
            occurrence=occurrence,
        )

    @classmethod
    def range(
        cls,
        start: int,
        end: int,
        *,
        expected_version: int | None = None,
    ) -> Selection:
        return cls(
            "range",
            start=start,
            end=end,
            expected_version=expected_version,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Selection:
        selection_type = value.get("type")
        if selection_type == "exact":
            return cls.exact(
                _required_string(value, "text"),
                occurrence=_optional_int(value, "occurrence"),
            )
        if selection_type == "context":
            return cls.context(
                before=_optional_string(value, "before"),
                text=_required_string(value, "text"),
                after=_optional_string(value, "after"),
                occurrence=_optional_int(value, "occurrence"),
            )
        if selection_type == "range":
            return cls.range(
                _required_int(value, "start"),
                _required_int(value, "end"),
                expected_version=_optional_int(value, "expected_version"),
            )
        raise InvalidOperationError(f"unknown selection type: {selection_type!r}")


def _required_string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str):
        raise InvalidOperationError(f"{key!r} must be a string")
    return result


def _optional_string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key, "")
    if not isinstance(result, str):
        raise InvalidOperationError(f"{key!r} must be a string")
    return result


def _required_int(value: Mapping[str, Any], key: str) -> int:
    result = value.get(key)
    if not isinstance(result, int):
        raise InvalidOperationError(f"{key!r} must be an integer")
    return result


def _optional_int(value: Mapping[str, Any], key: str) -> int | None:
    result = value.get(key)
    if result is not None and not isinstance(result, int):
        raise InvalidOperationError(f"{key!r} must be an integer")
    return result
