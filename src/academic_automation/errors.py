class BrowserError(RuntimeError):
    def __init__(self, message, code=1, details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}
