class LuxirError(Exception):
    """
    Base class for all errors raised by LuxirClient.
    """

    def __init__(self, message, request_id=None, code=None, kind=None, **kwargs):
        super().__init__(message)
        self.message = message
        self.request_id = request_id
        self.code = code
        self.kind = kind

    def __str__(self):
        parts = [self.message]
        if self.code:
            parts.append("code={}".format(self.code))
        if self.request_id:
            parts.append("request_id={}".format(self.request_id))
        return " ".join(parts)


class InvalidRequestError(LuxirError):
    """kind: invalid_request"""


class NotFoundError(LuxirError):
    """kind: not_found"""


class AlreadyExistsError(LuxirError):
    """kind: already_exists"""


class FailedPreconditionError(LuxirError):
    """kind: failed_precondition"""


class ResourceExhaustedError(LuxirError):
    """kind: resource_exhausted (HTTP 429) - safe to retry with backoff"""


class UnavailableError(LuxirError):
    """kind: unavailable - safe to retry"""


class InternalError(LuxirError):
    """kind: internal"""


class ConnectionError(LuxirError):
    """
    Raised when the client couldn't reach any configured host at all,
    as opposed to the server responding with an error envelope.
    """


# Maps the `kind` string from Luxir's error envelope
# ({"request_id", "error": {"kind", "code", "message"}}) to an exception class.
KIND_TO_EXC = {
    "invalid_request": InvalidRequestError,
    "not_found": NotFoundError,
    "already_exists": AlreadyExistsError,
    "failed_precondition": FailedPreconditionError,
    "resource_exhausted": ResourceExhaustedError,
    "unavailable": UnavailableError,
    "internal": InternalError,
}


def error_from_envelope(envelope):
    """
    Given a parsed Luxir error envelope dict, raise the matching LuxirError subclass.
    Falls back to the base LuxirError if `kind` is missing or unrecognized.
    """
    error = envelope.get("error", {}) or {}
    kind = error.get("kind")
    exc_cls = KIND_TO_EXC.get(kind, LuxirError)
    raise exc_cls(
        error.get("message", "Unknown Luxir error"),
        request_id=envelope.get("request_id"),
        code=error.get("code"),
        kind=kind,
    )
