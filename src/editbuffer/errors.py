class EditBufferError(Exception):
    """Base error for editbuffer."""


class TargetNotFoundError(EditBufferError):
    pass


class AmbiguousTargetError(EditBufferError):
    def __init__(self, candidates: tuple[tuple[int, int], ...]) -> None:
        self.candidates = candidates
        super().__init__(f"selection matched {len(candidates)} targets: {candidates}")


class FuzzyMatchError(EditBufferError):
    def __init__(
        self,
        reason: str,
        candidates: tuple[tuple[int, int, float], ...],
    ) -> None:
        self.reason = reason
        self.candidates = candidates
        super().__init__(f"fuzzy selection {reason}: {candidates}")


class InvalidOperationError(EditBufferError):
    pass


class StaleVersionError(EditBufferError):
    pass


class ValidationError(EditBufferError):
    pass
