from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from .errors import InvalidOperationError

SelectionType = Literal["exact", "context", "range", "fuzzy", "block"]


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
    threshold: float = 0.85
    ambiguity_margin: float = 0.05
    block_id: str | None = None

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
    def fuzzy(
        cls,
        text: str,
        *,
        threshold: float = 0.85,
        ambiguity_margin: float = 0.05,
    ) -> Selection:
        return cls(
            "fuzzy",
            text=text,
            threshold=threshold,
            ambiguity_margin=ambiguity_margin,
        )

    @classmethod
    def block(cls, block_id: str) -> Selection:
        return cls("block", block_id=block_id)

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
        if selection_type == "fuzzy":
            return cls.fuzzy(
                _required_string(value, "text"),
                threshold=_optional_float(value, "threshold", 0.85),
                ambiguity_margin=_optional_float(
                    value,
                    "ambiguity_margin",
                    0.05,
                ),
            )
        if selection_type == "block":
            return cls.block(_required_string(value, "block_id"))
        raise InvalidOperationError(f"unknown selection type: {selection_type!r}")

    def as_dict(self) -> dict[str, Any]:
        if self.type == "exact":
            result: dict[str, Any] = {"type": "exact", "text": self.text}
            if self.occurrence is not None:
                result["occurrence"] = self.occurrence
            return result
        if self.type == "context":
            result = {
                "type": "context",
                "before": self.before,
                "text": self.text,
                "after": self.after,
            }
            if self.occurrence is not None:
                result["occurrence"] = self.occurrence
            return result
        if self.type == "range":
            result = {"type": "range", "start": self.start, "end": self.end}
            if self.expected_version is not None:
                result["expected_version"] = self.expected_version
            return result
        if self.type == "fuzzy":
            return {
                "type": "fuzzy",
                "text": self.text,
                "threshold": self.threshold,
                "ambiguity_margin": self.ambiguity_margin,
            }
        return {"type": "block", "block_id": self.block_id}


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


def _optional_float(
    value: Mapping[str, Any],
    key: str,
    default: float,
) -> float:
    result = value.get(key, default)
    if not isinstance(result, (int, float)):
        raise InvalidOperationError(f"{key!r} must be a number")
    return float(result)
