from dataclasses import dataclass
from collections.abc import Iterator

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
