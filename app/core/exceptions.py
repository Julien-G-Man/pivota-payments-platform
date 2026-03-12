"""All typed application exceptions for TraderFlow."""


class TraderFlowError(Exception):
    """Base exception for all application errors."""


class FloatMoneyError(TraderFlowError):
    """Raised when float is passed to Money()."""


class CurrencyMismatchError(TraderFlowError):
    """Raised on arithmetic between different currencies."""


class DuplicateTransactionError(TraderFlowError):
    """Raised when idempotency check finds existing transaction."""


class IdempotencyConflictError(TraderFlowError):
    """Raised when idempotency key is acquired concurrently."""


class ComplianceHoldError(TraderFlowError):
    """Raised when a transaction is blocked by AML hold."""


class KYCRequiredError(TraderFlowError):
    """Raised when action requires completed KYC."""


class InsufficientFundsError(TraderFlowError):
    """Raised when account balance is insufficient."""


class MoMoAPIError(TraderFlowError):
    """Raised on MTN MoMo API errors."""


class WebhookSignatureError(TraderFlowError):
    """Raised when MoMo webhook HMAC signature fails verification."""


class SecretsError(TraderFlowError):
    """Raised when secret cannot be retrieved."""
