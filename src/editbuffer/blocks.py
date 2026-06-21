import re

from .resolver import ResolvedSelection

_FENCE = re.compile(
    r"^(?P<fence>`{3,}|~{3,})[^\n]*\beditbuffer:id=(?P<id>[A-Za-z0-9_.-]+)[^\n]*\n",
    re.MULTILINE,
)
_REGION = re.compile(
    r"^<!--\s*editbuffer:block\s+(?P<id>[A-Za-z0-9_.-]+)\s*-->\s*\n",
    re.MULTILINE,
)
_REGION_END = re.compile(r"^<!--\s*/editbuffer:block\s*-->", re.MULTILINE)


def find_blocks(content: str, block_id: str) -> tuple[ResolvedSelection, ...]:
    matches = list(_fenced_blocks(content, block_id))
    matches.extend(_regions(content, block_id))
    return tuple(sorted(matches, key=lambda match: match.start))


def _fenced_blocks(content: str, block_id: str):
    for opening in _FENCE.finditer(content):
        if opening.group("id") != block_id:
            continue
        fence = re.escape(opening.group("fence"))
        closing = re.search(rf"^{fence}[^\n]*(?:\n|$)", content[opening.end() :], re.MULTILINE)
        if closing:
            yield ResolvedSelection(
                opening.end(),
                opening.end() + closing.start(),
            )


def _regions(content: str, block_id: str):
    for opening in _REGION.finditer(content):
        if opening.group("id") != block_id:
            continue
        closing = _REGION_END.search(content, opening.end())
        if closing:
            yield ResolvedSelection(opening.end(), closing.start())
