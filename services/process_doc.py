# Importar la clase ReaderFactory desde seu módulo
from ifactory.factory import ReaderFactory

# -- Funciones Axiliares --
# Funcion formato
def obtener_extension(cadena: str) -> str:
    #variable que busca el ultimo punto
    ultimo_punto_indice = cadena.rfind('.')
    # parchando el error
    if ultimo_punto_indice == -1:
        return ""
    # si no devulve la extension
    return cadena[ultimo_punto_indice + 1:]

# ------- Me permite Validar uploads -------

# --- Clase Pirncipal ---
class ProcessDoc:
    # contructor
    def __init__(self, filename: str):
        self.filename = filename

    # Funcion para conexion con factory y obtener datos extraidos
    def process(self) -> str:
        file = self.filename
        ext = obtener_extension(file)

        # Inicializaremos get_info a "" para garantizar el retorno en caso de fallos
        get_info = ""

        if ext == "":
            # Archivo sin extensión: retorna "" (el valor inicial de get_info)
            print(f"[{file}] | Alerta! - Archivo SIN extension. No se puede procesar.")
            return get_info
        
        # Proceso con extensión
        try:
            # 1. Obtenemos la instancia(objeto) del objeto (ReaderPDF, ReaderTXT, etc.)
            doc_reader = ReaderFactory.get_reader_object(ext)

            #if ext == "pdf":
            #   return ReaderPDF()
            #elif ext == "txt":
            #   return ReaderTXT()


            # 2. LLamamos al metodo implementado
            get_info = doc_reader.get_reading(file)

            #si doc_reader es ReaderPDF
            #    → se ejecuta ReaderPDF.get_reading()

            # si es ReaderTXT
            #    → se ejecuta ReaderTXT.get_reading()

        except ValueError as e:
            # parche por si la extension no es soportada por la factory
            # get_info permanece como "", que es lo que se retornara al final
            print(f"[{file}] | Alerta! - Error al crear objeto para '{ext}': {e}.")
            return get_info ## retorna ""
        
        # 3. Verifico el resultado (SOLO SI NO HUBO ERROR EN LA FACTORY)

        if get_info == "":
            # Extesion soportada, pero el lector no pudo extraer datos.
            print(f"[{file}] | Alerta! - No podemos extraer datos de este tipo de archivo con la extesión. ")

        else:
            # Éxito: Mostramos la infomación extraida
            print(f"--- Obteniendo la informacion de {file} ({ext.upper()}) ---")
        
        # Retorna el contenido (si es exitoso) o "" (si no hay datos o hubo fallo)
        return get_info
    