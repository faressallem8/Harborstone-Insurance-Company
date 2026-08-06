class MemoryBaseException(Exception):
    """Base exception class for all memory operations."""
    pass


class MemoryOverflowError(MemoryBaseException):
    """Raised when token capacity exceeds maximum limits."""
    pass


class MemoryValidationError(MemoryBaseException):
    """Raised when memory invariant, sequence, or deduplication validations fail."""
    pass


class MemoryRollbackError(MemoryBaseException):
    """Raised when attempting a rollback with no available state snapshot."""
    pass


class StrategyExecutionError(MemoryBaseException):
    """Raised when context strategy execution fails."""
    pass


class TokenizationError(MemoryBaseException):
    """Raised when token estimation or calculation fails."""
    pass


class ConcurrencyError(MemoryBaseException):
    """Raised when thread lock or atomic state mutations fail."""
    pass