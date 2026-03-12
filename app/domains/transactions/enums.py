"""Transaction enums."""

import enum


class TransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    REVERSAL = "reversal"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


class Category(str, enum.Enum):
    AIRTIME = "airtime"
    TRANSFER = "transfer"
    MERCHANT = "merchant"
    UTILITY = "utility"
    SALARY = "salary"
    CASH_OUT = "cash_out"
    CASH_IN = "cash_in"
    LOAN = "loan"
    OTHER = "other"
