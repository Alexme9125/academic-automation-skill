class BrowserError(RuntimeError):
    def __init__(self, message, code=1, details=None):
        from .redaction import redact
        super().__init__(redact(message))
        self.code = code
        self.details = redact(details or {})
