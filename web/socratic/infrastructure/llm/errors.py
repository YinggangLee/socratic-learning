class LLMCallError(Exception):
    def __init__(self, message: str, attempts: int = 0):
        super().__init__(message)
        self.attempts = attempts


class LLMStreamError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
