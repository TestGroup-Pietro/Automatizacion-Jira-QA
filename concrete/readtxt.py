from ifactory.interface import ReadingInterface
from pathlib import Path

class ReadTXT(ReadingInterface):

    def get_reading(self, file: str) -> str:
        """
        LEE todo el contenido de texto de un archivo TXT
        :param file: La ruta (string) al archivo TXT.
        :return: Un string que contiene el texto completo del archivo
        """

        txt_path = Path(file)

        # 1. Validacion de Ruta
        # Verifica si el archivo existe
        if not txt_path.is_file():
            # Devuelve un mensaje de error si el archivo no se encuentra
            return f"Error: El Archivo no fue encontrado en la ruta {file}"
        
        try:
            # 2. Lectura del Contenido
            # Abrir el archivo en modo de Lectura ('r') y codificacion UTF-8 para compatibilidad
            with open(txt_path, 'r', encoding='utf-8') as f:
                # Lee todo el contenido del archivo
                text = f.read()

            # 3. Retorno 
            return text
        except FileNotFoundError:
            # Este error es capturado por la verificacion inicial, pero es bueno tenerlo
            return f"Error : Archivo TXT no encontrado en {file}."

        except Exception as e:
            # 4. Manejo de Errores (para oermisos, codificamos u otros problemas)
            return f"Error al leer el archivo TXT {file}: {e}"