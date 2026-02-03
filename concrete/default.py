from ifactory.interface import ReadingInterface

class DefaultClass(ReadingInterface):
    def get_reading(self, file: str):
        return ""