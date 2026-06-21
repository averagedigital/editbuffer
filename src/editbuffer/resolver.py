from dataclasses import dataclass
from difflib import SequenceMatcher

from .errors import (
    AmbiguousTargetError,
    FuzzyMatchError,
    InvalidOperationError,
    StaleVersionError,
    TargetNotFoundError,
)
from .selection import Selection


@dataclass(frozen=True, slots=True)
class ResolvedSelection:
    start: int
    end: int
    confidence: float = 1.0


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
        if selection.type == "block":
            from .blocks import find_blocks

            if not selection.block_id:
                raise InvalidOperationError("block_id must not be empty")
            return _choose(find_blocks(content, selection.block_id), None)
        if selection.text == "":
            raise InvalidOperationError("selection text must not be empty")

        if selection.type == "exact":
            candidates = _find_all(content, selection.text or "")
        elif selection.type == "context":
            candidates = _find_context(content, selection)
        else:
            return _find_fuzzy(content, selection)
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


def _find_fuzzy(content: str, selection: Selection) -> ResolvedSelection:
    text = selection.text or ""
    if not 0 < selection.threshold <= 1:
        raise InvalidOperationError("fuzzy threshold must be in (0, 1]")
    if not 0 <= selection.ambiguity_margin <= 1:
        raise InvalidOperationError("fuzzy ambiguity_margin must be in [0, 1]")

    variation = max(2, len(text) // 5)
    raw: list[ResolvedSelection] = []
    for length in range(max(1, len(text) - variation), len(text) + variation + 1):
        for start in range(0, len(content) - length + 1):
            score = SequenceMatcher(None, text, content[start : start + length]).ratio()
            raw.append(ResolvedSelection(start, start + length, score))

    candidates = _distinct_fuzzy_targets(raw, len(text))
    diagnostics = tuple(
        (candidate.start, candidate.end, round(candidate.confidence, 4))
        for candidate in candidates[:5]
    )
    if not candidates or candidates[0].confidence < selection.threshold:
        raise FuzzyMatchError("below_threshold", diagnostics)
    eligible = [
        candidate
        for candidate in candidates
        if candidate.confidence >= selection.threshold
    ]
    if (
        len(eligible) > 1
        and eligible[0].confidence - eligible[1].confidence
        < selection.ambiguity_margin
    ):
        raise FuzzyMatchError("ambiguous", diagnostics)
    return candidates[0]


def _distinct_fuzzy_targets(
    candidates: list[ResolvedSelection],
    query_length: int,
) -> list[ResolvedSelection]:
    ranked = sorted(candidates, key=lambda item: item.confidence, reverse=True)
    selected: list[ResolvedSelection] = []
    separation = max(1, query_length // 2)
    for candidate in ranked:
        center = (candidate.start + candidate.end) // 2
        if all(
            abs(center - (existing.start + existing.end) // 2) >= separation
            for existing in selected
        ):
            selected.append(candidate)
    return selected
