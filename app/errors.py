class TrialError(ValueError):
    def __init__(self, code, status=422, **detail):
        self.code, self.status, self.detail = code, status, detail
        super().__init__(code)
