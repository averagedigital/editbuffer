from dataclasses import dataclass

from .errors import (
    AmbiguousTargetError,
    InvalidOperationError,
    StaleVersionError,
    TargetNotFoundError,
)
from .selection import Selection


@dataclass(frozen=True, slots=True)
class ResolvedSelection:
    start: int
    end: int


class SelectionResolver:
    def resolve(
        self,
        content: str,
        selection: Selection,
        *,
        version: int,
    ) -> ResolvedSelection:
        if selection.type == "range":
            return self._resolve_range(content, selection, version)
        if selection.text == "":
            raise InvalidOperationError("selection text must not be empty")

        if selection.type == "exact":
            candidates = _find_all(content, selection.text or "")
        else:
            candidates = _find_context(content, selection)
        return _choose(candidates, selection.occurrence)

    def _resolve_range(
        self,
        content: str,
        selection: Selection,
        version: int,
    ) -> ResolvedSelection:
        if (
            selection.expected_version is not None
            and selection.expected_version != version
        ):
            raise StaleVersionError(
                f"expected version {selection.expected_version}, current version is {version}"
            )
        start, end = selection.start, selection.end
        if start is None or end is None or start < 0 or end < start or end > len(content):
            raise InvalidOperationError(
                f"invalid range [{start}, {end}) for content length {len(content)}"
            )
        return ResolvedSelection(start, end)


def _find_all(content: str, text: str) -> tuple[ResolvedSelection, ...]:
    matches: list[ResolvedSelection] = []
    start = 0
    while (index := content.find(text, start)) != -1:
        matches.append(ResolvedSelection(index, index + len(text)))
        start = index + 1
    return tuple(matches)


def _find_context(
    content: str,
    selection: Selection,
) -> tuple[ResolvedSelection, ...]:
    text = selection.text or ""
    needle = f"{selection.before}{text}{selection.after}"
    offset = len(selection.before)
    return tuple(
        ResolvedSelection(match.start + offset, match.start + offset + len(text))
        for match in _find_all(content, needle)
    )


def _choose(
    candidates: tuple[ResolvedSelection, ...],
    occurrence: int | None,
) -> ResolvedSelection:
    if not candidates:
        raise TargetNotFoundError("selection did not match the current buffer")
    if occurrence is not None:
        if occurrence < 0 or occurrence >= len(candidates):
            raise TargetNotFoundError(
                f"occurrence {occurrence} is outside {len(candidates)} matches"
            )
        return candidates[occurrence]
    if len(candidates) > 1:
        raise AmbiguousTargetError(tuple((match.start, match.end) for match in candidates))
    return candidates[0]
