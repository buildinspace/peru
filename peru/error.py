class PrintableError(Exception):
    def __init__(self, message, *args, **kwargs):
        self.message = message.format(*args, **kwargs)

    def __str__(self):
        return self.message
