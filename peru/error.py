class PrintableError(Exception):
    def __init__(self, msg=None):
        self.msg = msg
