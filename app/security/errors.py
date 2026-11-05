class AuthError(Exception):
    """401: identity could not be established."""


class AccessDenied(Exception):
    """403: identity known, action/resource not permitted. `incident_id` (optional) lets the audit trail link the denial."""

    def __init__(self, message: str = "", incident_id: str | None = None) -> None:
        super().__init__(message)
        self.incident_id = incident_id


class NotFound(Exception):
    """404 (also used instead of 403 when revealing existence would leak information)."""


class Conflict(Exception):
    """409: replay / duplicate / invalid state transition."""
