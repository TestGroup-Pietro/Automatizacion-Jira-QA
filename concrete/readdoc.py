from ifactory.interface import ReadingInterface
from pathlib import Path
from docx import Document # Importamos la clase Document de la libreria python-docx
from docx.opc.exceptions import PackageNotFoundError # importamos el error especifico para archivos

class ReadDOCX(ReadingInterface):
    def get_reading(self, file: str) -> str:
        """ Lee el contenido de texto de todos los parrafos de un archov DOCX.
         :param file: la ruta (string) al archivo DOCX.
         :return: Un string que contiene el texto concatenado de todos los parrafos.
         """
        docx_path = Path(file)

        #1. Validacion de Ruta
        # Varificar si el archivo existe
        if not docx_path.is_file():
            return f"Error: El archivo no fue encontrado en la ruta {file}"
        
        try:
            # 2. Lectura del Contenido
            # Abrir el documento DOCX
            document = Document(docx_path)
            text = []

            # Iterar sobre todos los parrafos del documento
            for paragraph in document.paragraphs:
                # Añadir el texto del parrafo a la lista
                text.append(paragraph.text)

            # Unir todos los texto de los párrafos con un salto de linea
            return "\n".join(text)
        
        except PackageNotFoundError:
            # Manejo de errores especificos de docx (ej. archivo corrupto o no es un DCOX válido)
            return f"Error al leer el archivo DOCX {file}: El archivo no es un documento de Word válido"
        
        except Exception as e:
            # 3. Manejo de Errores (para permisos u otros problemas no capturados antes)
            return f"Error inesperado al leer el arvhico DOCX{file}: {e}"