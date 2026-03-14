"""All typed application exceptions for Pivota."""


class PivotaError(Exception):
    """Base exception for all application errors."""


class FloatMoneyError(PivotaError):
    """Raised when float is passed to Money()."""


class CurrencyMismatchError(PivotaError):
    """Raised on arithmetic between different currencies."""


class DuplicateTransactionError(PivotaError):
    """Raised when idempotency check finds existing transaction."""


class IdempotencyConflictError(PivotaError):
    """Raised when idempotency key is acquired concurrently."""


class ComplianceHoldError(PivotaError):
    """Raised when a transaction is blocked by AML hold."""


class KYCRequiredError(PivotaError):
    """Raised when action requires completed KYC."""


class InsufficientFundsError(PivotaError):
    """Raised when account balance is insufficient."""


class MoMoAPIError(PivotaError):
    """Raised on MTN MoMo API errors."""


class WebhookSignatureError(PivotaError):
    """Raised when MoMo webhook HMAC signature fails verification."""


class SecretsError(PivotaError):
    """Raised when secret cannot be retrieved."""
