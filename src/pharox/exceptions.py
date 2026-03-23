"""Custom exception hierarchy for the Pharox toolkit."""


class PharoxError(Exception):
    """Base exception for all pharox errors."""


class PoolNotFoundError(PharoxError):
    """Raised when a pool cannot be found."""


class ProxyNotFoundError(PharoxError):
    """Raised when a proxy cannot be found."""


class ProxyUnavailableError(PharoxError):
    """Raised when a proxy is no longer available for leasing."""


class ConsumerNotFoundError(PharoxError):
    """Raised when a consumer cannot be found."""


class InvalidLeaseError(PharoxError):
    """Raised when lease parameters are invalid."""
