class SDKError(Exception):
    """Stable category and operation; remote bodies and secrets are never formatted."""

    def __init__(self, kind: str, operation: str, *, status: int = 0, code: str = ""):
        self.kind = kind
        self.operation = operation
        self.status = status
        self.code = code
        super().__init__(f"{operation}: {kind} (HTTP {status})")
