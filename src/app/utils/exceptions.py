class NotFoundException(Exception):
    def __init__(self, name: str):
        self.name = name

class InvalidException(Exception):
    def __init__(self, name: str):
        self.name = name
