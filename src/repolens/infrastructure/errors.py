"""Sanitized source-boundary failures; never include uncontrolled Git output."""


class AcquisitionError(Exception):
    """Repository acquisition or inventory could not be completed safely."""


class InvalidSource(AcquisitionError):
    """Invalid URL/path, or unsupported local repository shape."""


class GitUnavailable(AcquisitionError):
    """A trusted Git executable is unavailable."""


class GitFailed(AcquisitionError):
    """Git failed, exceeded output bounds, or returned invalid metadata."""


class GitTimedOut(GitFailed):
    """The Git operation exceeded its deadline."""


class TraversalLimitExceeded(AcquisitionError):
    """Traversal exceeded a declared entry/depth bound."""
