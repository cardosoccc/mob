"""Service layer - shared business logic between API and CLI."""


class ServiceError(Exception):
    """Error raised by service functions."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
