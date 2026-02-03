from abc import ABC, abstractmethod

class ReadingInterface(ABC):    
    @abstractmethod
    def get_reading(self, file: str):
        pass # Esto es como el void en Java para decir que no devuelve nada