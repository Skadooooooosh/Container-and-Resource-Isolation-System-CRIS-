class CrisError(Exception):
    status = 500
    code = "internal_error"

    def __init__(self, message: str, **detail):
        super().__init__(message)
        self.message, self.detail = message, detail


class NotFound(CrisError):
    status, code = 404, "not_found"


class InvalidTransition(CrisError):
    status, code = 409, "invalid_transition"


class Unsupported(CrisError):
    status, code = 422, "unsupported_on_host"


class ValidationFailed(CrisError):
    status, code = 422, "validation_error"


class LaunchFailed(CrisError):
    status, code = 500, "launch_failed"
