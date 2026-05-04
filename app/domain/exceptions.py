from __future__ import annotations


class DomainError(Exception):
    """Base class for expected domain violations (mapped to HTTP responses)."""


class HotelDiscoveryFailed(DomainError):
    """Google/stub hotel discovery could not complete (mapped to HTTP by the API layer)."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ApprovalRequiredError(DomainError):
    """Raised when a booking is attempted without prior quote approval."""
