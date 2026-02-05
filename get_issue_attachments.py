import os
import sys
import asyncio
from pathlib import Path
from urllib import response
import httpx # Reemplazo moderno y asíncrono de 'requests'
from requests.auth import HTTPBasicAuth # Se mantiene para la autenticación básica
import base64

# =========================================================================
# IMPORTACIÓN DE SERVICIOS
# (Asumimos que estos servicios son síncronos o no pueden ser fácilmente refactorizados a async)
# =========================================================================
try:
    # Nota: Si ProcessDOC, send_chat, createxlsx, y upload_attachment_to_jira
    # tienen llamadas a API o I/O internas que son lentas, 
    # se beneficiarían de ser refactorizadas a async/await internamente.
    # Por ahora, los ejecutaremos dentro de un threadpool con asyncio.to_thread().
    from services.process_doc import ProcessDOC
    from services.email import enviar_email
#    from services.iachat import send_chat
#    from services.formatxlsx import createxlsx
    from services.upload_attachment_to_jira import upload_attachment_to_jira
except ImportError as e:
    print(f"ERROR CRÍTICO de importación: {e}. Verifique la estructura de carpetas de 'services'.")
    sys.exit(1)
# =========================================================================

# --- CONFIGURACIÓN DE ENTORNO ---
JIRA_URL = os.getenv('URL_JIRA')
JIRA_USER = os.getenv('USER_JIRA')
JIRA_TOKEN = os.getenv('JIRA_TOKEN')
ISSUE_KEY = os.getenv('ISSUE_KEY')
TARGET_DIR = os.getenv('TARGET_DIR')
ATTACHMENT_ENDPOINT = f"{JIRA_URL}/rest/api/3/issue/{ISSUE_KEY}?fields=attachment"
# Token Xray
XRAY_ID = os.getenv('XRAY_ID')
XRAY_PASSWORD = os.getenv('XRAY_CLIENT')
XRAY_AUTH = os.getenv('XRAY_URL_AUTH')
XRAY_GRAPHQL = os.getenv('XRAY_URL_GRAPHQL')


# Lista global para almacenar los metadatos de los adjuntos de Jira (payload)
# Ahora no es estrictamente necesario que sea global si se maneja como retorno/parámetro.
# La mantendremos para coherencia, pero la pasaremos como parámetro.
attachments = [] 



# --- FUNCIO DE XRAY TOKEN PARA TESTPLAN ---
async def get_xray_token():
    """Obtiene el token de acceso de Xray usando OAuth."""
    url = XRAY_AUTH
    payload = {
        "client_id": XRAY_ID, 
        "client_secret": XRAY_PASSWORD
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.text.replace('"', '')

async def generar_documento_xray(token, issue_key):
    """Busca la plantilla usando getTestPlans con los campos correctos para Xray Cloud."""
    url = XRAY_GRAPHQL
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 1. PASO DE DESCUBRIMIENTO
    # Cambiamos 'id' por 'issueId' que es el estándar para el tipo TestPlan en Xray Cloud
    query = """
    {
        getTestPlans(limit: 20) {
            results {
                issueId
                jira(fields: ["summary"])
            }
        }
    }
    """
    
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json={"query": query}, headers=headers)
        data = res.json()
        
        if "errors" in data:
            # Si issueId también falla, intentamos una query genérica de búsqueda
            print(f"   [DEBUG] Reintentando búsqueda alternativa...")
            query = "{ getTemplates(limit: 20) { results { id name } } }"
            res = await client.post(url, json={"query": query}, headers=headers)
            data = res.json()

        # Extracción flexible de resultados
        templates = []
        if "data" in data and data["data"]:
            first_key = list(data["data"].keys())[0]
            templates = data["data"][first_key].get("results", [])

        if not templates:
            raise Exception("No se encontraron plantillas o Test Plans disponibles en Xray.")

        # 2. SELECCIÓN DE LA PLANTILLA
        # Intentamos buscar por el nombre que aparece en tu imagen: "Plantilla prueba"
        selected = None
        for t in templates:
            # Buscamos el nombre en el campo 'name' o dentro del objeto 'jira' summary
            summary = t.get('jira', {}).get('summary', '')
            name = t.get('name', '')
            if "Plantilla prueba" in summary or "Plantilla prueba" in name:
                selected = t
                break
        
        if not selected:
            selected = templates[0]
            
        # Obtenemos el ID (puede venir como 'id' o 'issueId')
        template_id = selected.get('issueId') or selected.get('id')
        print(f"   -> [Xray] ID detectado: {template_id}")

        # 3. GENERACIÓN
        gen_mutation = """
        mutation ($issueKey: String!, $templateId: String!) {
            generateDocument(issueKey: $issueKey, templateId: $templateId, outputFormat: "docx") {
                reportFilename
                reportContent
            }
        }
        """
        variables = {"issueKey": issue_key, "templateId": str(template_id)}
        res_gen = await client.post(url, json={"query": gen_mutation, "variables": variables}, headers=headers)
        data_gen = res_gen.json()
        
        if 'errors' in data_gen:
            raise Exception(f"Error en generación: {data_gen['errors'][0].get('message')}")
            
        report = data_gen['data']['generateDocument']
        return report['reportFilename'], report['reportContent']

# --- FUNCION CREAR SUBTASK ESTRUCTURA CARPETAS ---
def crear_subtarea_jira(parent_key, titulo):
    """
    Crea una subtarea real en Jira vinculada al ticket padre.
    """
    url = f"{JIRA_URL}/rest/api/3/issue"
    auth = (JIRA_USER, JIRA_TOKEN)
    headers = {
        "Accept": "application/json", 
        "Content-Type": "application/json"
    }
    
    project_key = parent_key.split('-')[0]

    # PAYLOAD DEFINITIVO PARA SUBTAREAS
    payload = {
        "fields": {
            "project": {"key": parent_key.split('-')[0]},
            "parent": {"key": parent_key},
            "summary": titulo,
            "issuetype": {"name": "Subtask"} # El nombre mágico que descubrimos
        }
    }

    try:
        with httpx.Client(auth=auth) as client:
            response = client.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                subtask_key = response.json().get("key") # Capturamos la KEY de la subtarea
                print(f"   [Jira] Subtarea creada: {titulo} ({subtask_key})")
                return subtask_key # Retornamos la key
            else:
                print(f"[Jira] Error {response.status_code}: {response.text}")
                return None
    except Exception as e:
        print(f"   [Jira] Error de conexión: {e}")
        return None

# --- FUNCIONES ASÍNCRONAS ---

async def fetch_jira_attachments_metadata(client: httpx.AsyncClient) -> list:
    """Conecta a la API de Jira y obtiene los metadatos de los adjuntos."""
    global attachments # Para mantener la compatibilidad con la función de correo

    if not all([JIRA_URL, JIRA_USER, JIRA_TOKEN, ISSUE_KEY, TARGET_DIR]):
        print("ERROR CRÍTICO: Faltan credenciales o la ruta dinámica (TARGET_DIR) no se exportó.")
        sys.exit(1)
        
    print(f"1. Buscando adjuntos para: {ISSUE_KEY}")
    
    try:
        response = await client.get(ATTACHMENT_ENDPOINT, timeout=30.0)
        response.raise_for_status() 
        issue_data = response.json()
        attachments = issue_data.get('fields', {}).get('attachment', []) # Asignamos al global
        return attachments
    except httpx.RequestError as e:
        print(f"ERROR al conectar con la API de Jira: {e}")
        sys.exit(1)

async def download_single_attachment(client: httpx.AsyncClient, attachment: dict, target_dir: str) -> bool:
    filename = attachment['filename']
    content_url = attachment['content']
    filepath = Path(target_dir) / filename

    # --- FILTRO DE ARCHIVOS ---
    if "hu" not in filename.lower():
        print(f"   -> Omitiendo '{filename}': No contiene el prefijo 'hu'.")
        return False
    # ---------------------------
    
    print(f"   -> Iniciando descarga: {filename}")
    
    try:
        # [MODIFICACIÓN CLAVE]: Usamos client.get() en lugar de client.stream().
        # Esto permite que httpx gestione automáticamente la redirección 303,
        # y la respuesta final (file_response) será la que contenga el archivo real (código 200).
        file_response = await client.get(content_url, follow_redirects=True, timeout=None)
        
        # Ahora, raise_for_status() se ejecuta en la respuesta 200 OK final, o falla solo si es 4xx/5xx.
        file_response.raise_for_status()
        
        # [MODIFICACIÓN CLAVE]: Guardamos todo el contenido de una vez (file_response.content).
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            f.write(file_response.content)
            
        print(f"   -> Guardado OK: {filepath.name}")
        return True
        
    except httpx.RequestError as e:
        print(f"ERROR al descargar '{filename}': {e}")
        return False

def generate_folder_structure(base_path: Path, filename: str) -> Path:
    """
    Crea la estructura de carpetas requerida y el archivo Test Plan.
    Retorna la ruta del archivo Test Plan generado.
    """
    
    # Limpiamos el nombre para crear una carpeta contenedora limpia
    folder_name = filename.rsplit('.', 1)[0] # Quita la extension
    root_hu_path = base_path / folder_name

    # Definimos 3 carpetas solicitadas
    folders = [
        "Estrategias de pruebas",
        "Analisis y diseño de las pruebas",
        "Ejecucion de pruebas"
    ]

    # 1. Crea directorios
    for folder in folders:
        (root_hu_path / folder).mkdir(parents=True, exist_ok=True)

    return root_hu_path / "Estrategias de pruebas"
    
    # 2. Crear el documento 'Test Plan' dentro de 'Estrategias de pruebas'


    # test_plan_path = root_hu_path / "Estrategias de pruebas"  # / f"Test Plan - {folder_name}.txt" se cambia para el - XrayTestplan

    # Contenido plantilla del Test Plan
    # content = f"""=======================================
    # TEST PLAN GENERADO AUTOMÁTICAMENTE
    # ========================================
    # Archivo Origen: {filename}
    # Fecha Generacion: {sys.version}

    # 1. ALCANCE
    #    - Pruebas funcionales para la historia: {folder_name}

    # 2 ESTRATEGIAS
    #    - Tipos de prueba: Funcionales, Regresión.

    # 3. RECURSOS y HERRAMIENTAS
    #    - Jira / Xray

    # 4. CRITERIOS DE ACEPTACIÓN
    #    (A definir según análisis de la HU adjunta)
    # """
    # 	with open(test_plan_path, 'w', encoding='utf-8') as f:
    # 		f.write(content)

    # 	return test_plan_path

async def process_single_file(filepath: Path) -> str | None:
   """
    MODIFICADO: Procesa el archivo, crea carpetas locales y crea subtareas en Jira.
    """
    # 1. Filtramos por 'hu' como pediste
   if 'hu' not in filepath.name.lower():
        return None
   
   # Variable para el print (filepath.stem es el nombre sin .docx)
   hu_name = filepath.stem
   print(f"\n--- Procesando HU: {hu_name} ---")

   # --- NUEVA LÓGICA PIETRO: Creación de subtareas antes del flujo síncrono ---
   # Esto se hace aquí para aprovechar el contexto asíncrono
   subtareas_titulos = [
        "Estrategia de Pruebas",
        "Analisis y diseño de pruebas",
        "Ejecucion de pruebas"
    ]
    
   subtask_estrategia_key = None # Aquí guardaremos la key específica


   print(f"   -> Creando subtareas visuales en Jira para {ISSUE_KEY}...")
   for titulo in subtareas_titulos:
        # Usamos to_thread para la creación de subtareas individuales
        key_creada = await asyncio.to_thread(crear_subtarea_jira, ISSUE_KEY, titulo)

        # Si es la de estrategia, la guardamos para subir el archivo ahí
        if titulo == "Estrategia de Pruebas":
            subtask_estrategia_key = key_creada

    # Esta es la CLAVE: Ejecuta la función síncrona en un hilo separado
    # y espera el resultado de forma asíncrona.
    
   def sync_processing_workflow(target_subtask_key):
        try:
            # 1. Creamos carpetas basadas en la HU
            estrategia_folder = generate_folder_structure(filepath.parent, filepath.name)
            
            # 2. Buscamos si existe un archivo de Test Plan generado en la raíz para moverlo
            target_path = filepath.parent
            for xray_file in target_path.glob("*.docx"):
                # Si el nombre NO tiene 'hu', asumimos que es el de Xray generado (ej: SCRUM-36.docx)
                if 'hu' not in xray_file.name.lower():
                    destino_xray = estrategia_folder / xray_file.name
                    xray_file.rename(destino_xray)
                    print(f"   [Xray] Movido a Estrategias: {xray_file.name}")
                    
                    # Subir a Jira
                    success = upload_attachment_to_jira(
                        destino_xray, target_subtask_key, 
                        JIRA_URL, JIRA_USER, JIRA_TOKEN
                    )
                    return destino_xray.name if success else None
            
            return None
        except Exception as e:
            print(f"   [Error] {e}")
            return None
   return await asyncio.to_thread(sync_processing_workflow, subtask_estrategia_key)
   #Esto basicamente dice que retorna lo siguiente:

   # Un Texto (str): El nombre del archivo generado (ej: "Test Plan - HU_Login.txt") 
   # si todo salió bien (se crearon las carpetas y se subió a Jira).

   # Nada (None): Si hubo algún error o falló la subida.

async def main():

    """Función principal asíncrona que coordina todas las tareas. (Orquesta la descarga, creación de carpetas y notificación)"""
    # Usamos la variable globales para almacenar metadatos y la ruta destino
    global attachments, TARGET_DIR

    # 1. VALIDACIÓN INICIAL
    # Obtenemos la ruta donde se guardaran los archivos desde las variables de entorno
    TARGET_DIR = os.getenv('TARGET_DIR')
    current_issue_key = os.getenv('ISSUE_KEY')

    # Si no existe la ruta de destino, detenemos el script por seguridad
    if not TARGET_DIR or not current_issue_key:
        print("ERROR: TARGET_DIR o ISSUE_KEY no configurados en el entorno.")
        sys.exit(1)

    # 2. CONFIGURACIÓN DE CONEXIÓN JIRA
    # Preparamos la autenticación básica (Usuario + Token) para JIRA
    auth = HTTPBasicAuth(JIRA_USER, JIRA_TOKEN) # permite alamcenar las credenciales de jira
    
    # Iniciamos el cliente HTTP asíncrono (httpx)
    # Usamos 'async with' para segurar que la conexion se cierre correctamente al terminar
    # httpx.AsyncClient es crucial para manejar la concurrencia eficiente
    async with httpx.AsyncClient(auth=auth, headers={"Accept": "application/json"}) as client:
        
        # --- FASE 1: DESCARGA ---
        
        # 1. Obtener metadatos
        # llamamos a la API de Jira para obtener la lista de archivos adjuntos del ticket
        print(f"1. Obteniendo adjuntos de {current_issue_key}...")
        attachments_metadata = await fetch_jira_attachments_metadata(client)
        
        # Si la lista está vacia, no hay nada que hacer, terminamos aquí. 
        if not attachments_metadata:
            print("No se encontraron archivos adjuntos para descargar. Proceso finalizado.")
            return

        print(f"2. {len(attachments_metadata)} adjuntos encontrados. Descargando de forma CONCURRENTE en '{TARGET_DIR}'...")
        
        # 2. Iniciar tareas de descarga concurrentes
        # Creamos una lista de 'tasks' (tareas asíncronas)(cada "task" es una descarga individual)
        download_tasks = [
            download_single_attachment(client, attachment, TARGET_DIR) 
            for attachment in attachments_metadata
        ]
        
        # Esperamos a que todas las descargas finalicen (se ejecutan en paralelo/concurrencia)
        # asyncio.gather ejecuta dotas las descargas a la vez, primero espera y luego devuelve la lista de resultados
        download_results = await asyncio.gather(*download_tasks)
        download_count = sum(download_results) # Contamos cuántas descargas fueron exitosas
        
        print(f"3. Proceso de descarga finalizado. Total descargado: {download_count}")
        
        # si no descargo nada, se sale
        if download_count == 0:
            print("No se descargó ningún archivo. No hay nada que procesar.")
            return
        

#----------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------

        # --- FASE 2: GENERACIÓN AUTOMÁTICA DE XRAY ---
        # -- Modificacion Pietro --
        print("\n4. Generando Test Plan automáticamente desde Xray...")
        try:
            xray_token = await get_xray_token()
            # La función ahora hace todo: busca el ID y genera el archivo
            fname_xray, content_b64 = await generar_documento_xray(xray_token, current_issue_key)
            
            xray_path = Path(TARGET_DIR) / fname_xray
            with open(xray_path, "wb") as f:
                f.write(base64.b64decode(content_b64))
            print(f"   -> [Éxito] Documento '{fname_xray}' guardado en {TARGET_DIR}")
        except Exception as e:
            print(f"   -> [Aviso] Falló la fase de Xray: {e}")

        # --- FASE 3: PROCESAMIENTO (CREACIÓN DE CARPETAS) ---
        target_path = Path(TARGET_DIR)
        print("\n5. Creando estructuras de carpetas y subtareas...")
        files_to_process = [p for p in target_path.iterdir() if p.is_file() and 'hu' in p.name.lower()]
        
        if files_to_process:
            processed_results = await asyncio.gather(*(process_single_file(f) for f in files_to_process))
            archivos_generados = [name for name in processed_results if name is not None]
        else:
            print("   -> No hay archivos 'hu' para procesar.")
            archivos_generados = []

        # --- FASE 4: EMAIL ---
        if archivos_generados or (download_count > 0):
            print("\n6. Enviando notificación por correo...")
            # Aquí podrías añadir el nombre del archivo de Xray a la lista si quieres
            await asyncio.to_thread(enviar_email, archivos_generados, current_issue_key)
        else:
            print("\n6. No se enviará correo.")

        
        
        # --- FASE 4: NOTIFICACIÓN FINAL y REPORTE ---
        
        # Creamos una lista final para el reporte del correo
        archivos_finales = list(archivos_generados)

        # Añadimos nombres de archivos originales descargados
        for attachment in attachments_metadata:
            fname = attachment.get('filename', '')
            if 'hu' in fname.lower():
                archivos_finales.append(fname)

        """
        Qué hace: Inicia un bucle (ciclo).
        Traducción: "Para cada elemento (al que llamaremos attachment) que se encuentre dentro de la lista attachments"
        La lista attachments contiene toda la información cruda que bajamos de Jira al principio (nombre, tamaño, link de descarga, autor, etc.).
        """

        # Eliminar duplicados por seguridad (convertir a set y luego a list)
        archivos_finales = list(set(archivos_finales))
        
        # Verificamos si se generó algún trabajo nuevo
        if archivos_generados:
            print("\n6. Enviando notificación por correo electrónico.")
            # Enviamos el email. Usamos 'asyncio.to_thread' porque 'enviar_email'
            # es una funcion asincrona (bloqueante) y no queremos congelar el script
            await asyncio.to_thread(enviar_email, archivos_finales, current_issue_key)
        else:
            print("\n6. No se enviará correo. No se generaron archivos XLSX.")





# --- PUNTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":

    try:
        # Inicia el bucle de eventos de asyncio y ejecuta la función 'main'
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProceso interrumpido por el usuario.")
        sys.exit(1)