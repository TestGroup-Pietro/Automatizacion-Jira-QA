# Importaciones del punto anterior
from concrete.readpdf import ReadPDF
from concrete.readdoc import ReadDOCX
from concrete.readtxt import ReadTXT
#from concrete.readxls import READXLS
from concrete.default import DefaultClass
from ifactory.interface import ReadingInterface # Type: hiting

class ReaderFactory:
    # El método estico no necesita una instancia de la clase para ser llamado.
    # solo crea y devuelve objetos
    @staticmethod
    def get_reader_object(extension: str) -> ReadingInterface: # ReadingInterface: devuelve una intacia de redadEXTENSION
        extension = extension.lower()

        if extension == "pdf":
            return ReadPDF() #Crea y retorna una instancia de ReadPDF
        elif extension == "txt":
            return ReadTXT() #Crea y retorna una instancia de ReadTXT
        elif extension == "docx" or extension == "doc":
            return ReadDOCX() #Crea y retorna una instancia de ReadDOCX
        else:
            return DefaultClass #Crea y retorna una instancia por defecto
        
        


