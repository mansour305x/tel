from __future__ import annotations


class ValidationError(Exception):
    pass


class UnsupportedPlatformError(Exception):
    pass


class DownloadError(Exception):
    pass


class RetryLimitExceededError(Exception):
    pass


class JobCancellationError(Exception):
    pass
