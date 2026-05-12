class EvalOSError(Exception):
    """Base class for EvalOS errors."""


class ProviderError(EvalOSError):
    """Provider call failed."""


class CriteriaError(EvalOSError):
    """Criteria generation failed."""


class EvaluationError(EvalOSError):
    """Evaluation failed."""


class RepairError(EvalOSError):
    """Repair failed."""


class RetryError(EvalOSError):
    """Retries exhausted."""


class TimeoutError(EvalOSError):
    """Operation timed out."""
