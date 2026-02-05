import os
import sys
import asyncio
import base64
import httpx
import shutil
import tempfile
from pathlib import Path
from requests.auth import HTTPBasicAuth

# =========================================================================
# IMPORTACIÓN DE SERVICIOS EXTERNOS
# =========================================================================
try:
    from services.process_doc import ProcessDOC
    from services.email import enviar_email
    from services.upload_attachment_to_jira import upload_attachment_to_jira
except ImportError as e:
    print(f"ERROR CRÍTICO de importación: {e}. Verifique la carpeta 'services'.")
    sys.exit(1)

# =========================================================================
# CONFIGURACIÓN DE ENTORNO (VARIABLES GLOBALES)
# =========================================================================
JIRA_URL = os.getenv('URL_JIRA')
JIRA_USER = os.getenv('USER_JIRA')
JIRA_TOKEN = os.getenv('JIRA_TOKEN')
ISSUE_KEY = os.getenv('ISSUE_KEY')
TARGET_DIR = os.getenv('TARGET_DIR')
ATTACHMENT_ENDPOINT = f"{JIRA_URL}/rest/api/3/issue/{ISSUE_KEY}?fields=attachment"

# Credenciales Xray
XRAY_ID = os.getenv('XRAY_ID')
XRAY_PASSWORD = os.getenv('XRAY_CLIENT')
XRAY_AUTH = os.getenv('XRAY_URL_AUTH')

# Lista global para metadatos de adjuntos
attachments = [] 

# =========================================================================
# FUNCIONES DE APOYO - XRAY
# =========================================================================

async def get_xray_token():
    """Obtiene el token OAuth para autenticarse con la API de Xray Cloud."""
    url = XRAY_AUTH
    payload = {"client_id": XRAY_ID, "client_secret": XRAY_PASSWORD}
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.text.replace('"', '')

async def generar_documento_xray(token, issue_key):
    """
    Solicita a Xray la generación del Test Plan.
    Descarga el contenido binario y lo retorna para ser procesado.
    """
    # Usamos el endpoint REST v2 por ser más estable que GraphQL para descargas
    url = "https://xray.cloud.getxray.app/api/v2/documentgenerator/generate"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Payload: templateId 1 suele ser el reporte estándar de Test Plan
    payload = {
        "templateId": 1, 
        "issueKey": issue_key,
        "outputFormat": "docx"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=60.0)
        if response.status_code == 200:
            # Retornamos un nombre genérico y el contenido binario (raw)
            return f"TestPlan_{issue_key}.docx", response.content
        else:
            raise Exception(f"Error Xray API: {response.status_code}")

# =========================================================================
# FUNCIONES DE APOYO - JIRA Y SISTEMA DE ARCHIVOS
# =========================================================================

def crear_subtarea_jira(parent_key, titulo):
    """Crea una subtarea en Jira asociada al ticket padre (HU)."""
    url = f"{JIRA_URL}/rest/api/3/issue"
    auth = (JIRA_USER, JIRA_TOKEN)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    payload = {
        "fields": {
            "project": {"key": parent_key.split('-')[0]},
            "parent": {"key": parent_key},
            "summary": titulo,
            "issuetype": {"name": "Subtask"}
        }
    }

    try:
        with httpx.Client(auth=auth) as client:
            response = client.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                key = response.json().get("key")
                print(f"   [Jira] Subtarea creada: {titulo} ({key})")
                return key
            return None
    except Exception as e:
        print(f"   [Jira] Error: {e}")
        return None

def generate_folder_structure(base_path: Path, filename: str) -> Path:
    """Crea el árbol de carpetas local para organizar los documentos de la HU."""
    folder_name = filename.rsplit('.', 1)[0]
    root_hu_path = base_path / folder_name
    folders = ["Estrategias de pruebas", "Analisis y diseño de las pruebas", "Ejecucion de pruebas"]

    for folder in folders:
        (root_hu_path / folder).mkdir(parents=True, exist_ok=True)

    return root_hu_path / "Estrategias de pruebas"

async def fetch_jira_attachments_metadata(client: httpx.AsyncClient) -> list:
    """Obtiene la lista de adjuntos disponibles en el ticket de Jira."""
    global attachments
    try:
        response = await client.get(ATTACHMENT_ENDPOINT, timeout=30.0)
        response.raise_for_status()
        attachments = response.json().get('fields', {}).get('attachment', [])
        return attachments
    except Exception as e:
        print(f"Error metadatos Jira: {e}")
        sys.exit(1)

async def download_single_attachment(client: httpx.AsyncClient, attachment: dict, target_dir: str) -> bool:
    """Descarga un archivo adjunto de Jira si cumple con el filtro 'hu'."""
    filename = attachment['filename']
    if "hu" not in filename.lower():
        return False
    
    filepath = Path(target_dir) / filename
    try:
        response = await client.get(attachment['content'], follow_redirects=True, timeout=None)
        response.raise_for_status()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Error descargando {filename}: {e}")
        return False

# =========================================================================
# PROCESAMIENTO PRINCIPAL DE ARCHIVOS
# =========================================================================

async def process_single_file(filepath: Path) -> str | None:
    """Coordina la creación de subtareas, carpetas y subida de archivos de Xray."""
    if 'hu' not in filepath.name.lower():
        return None
    
    print(f"\n--- Procesando HU: {filepath.stem} ---")
    subtareas = ["Estrategia de Pruebas", "Analisis y diseño de pruebas", "Ejecucion de pruebas"]
    subtask_estrategia_key = None

    # 1. Crear subtareas en Jira
    for titulo in subtareas:
        key = await asyncio.to_thread(crear_subtarea_jira, ISSUE_KEY, titulo)
        if titulo == "Estrategia de Pruebas":
            subtask_estrategia_key = key

    # 2. Workflow de organización de archivos (Mover Xray de temporal a Estrategias)
    def sync_processing_workflow(target_subtask_key):
        try:
            # Crear carpetas locales
            estrategia_folder = generate_folder_structure(filepath.parent, filepath.name)
            
            # Buscar el archivo de Xray que bajamos previamente al TARGET_DIR
            for xray_file in filepath.parent.glob("*.docx"):
                if 'hu' not in xray_file.name.lower(): # Los de Xray no llevan 'hu' en el nombre
                    destino = estrategia_folder / xray_file.name
                    shutil.move(str(xray_file), str(destino))
                    print(f"   [Sistema] Archivo Xray movido a: {destino.name}")
                    
                    # Subir el archivo a la subtarea de Jira correspondiente
                    success = upload_attachment_to_jira(
                        destino, target_subtask_key, JIRA_URL, JIRA_USER, JIRA_TOKEN
                    )
                    return destino.name if success else None
            return None
        except Exception as e:
            print(f"   [Error Workflow] {e}")
            return None

    return await asyncio.to_thread(sync_processing_workflow, subtask_estrategia_key)

# =========================================================================
# FUNCIÓN MAIN (ORQUESTADOR)
# =========================================================================

async def main():
    global attachments, TARGET_DIR
    current_issue_key = ISSUE_KEY

    if not TARGET_DIR or not current_issue_key:
        print("ERROR: Variables de entorno insuficientes.")
        sys.exit(1)

    auth = HTTPBasicAuth(JIRA_USER, JIRA_TOKEN)
    
    async with httpx.AsyncClient(auth=auth, headers={"Accept": "application/json"}) as client:
        
        # FASE 1: DESCARGA DE ADJUNTOS 'HU'
        print(f"1. Buscando adjuntos en {current_issue_key}...")
        meta = await fetch_jira_attachments_metadata(client)
        if not meta: return

        tasks = [download_single_attachment(client, att, TARGET_DIR) for att in meta]
        results = await asyncio.gather(*tasks)
        download_count = sum(results)
        print(f"2. Descargas finalizadas: {download_count}")

        if download_count == 0: return

        # FASE 2: GENERACIÓN DE XRAY (Transito a Carpeta Temporal)
        print("\n3. Generando Test Plan desde Xray...")
        try:
            token = await get_xray_token()
            # Descargamos el reporte (binario)
            filename, content = await generar_documento_xray(token, current_issue_key)
            
            # Lo guardamos temporalmente en el TARGET_DIR para que process_single_file lo encuentre
            temp_xray_path = Path(TARGET_DIR) / filename
            with open(temp_xray_path, "wb") as f:
                f.write(content)
            print(f"   -> [Xray] Documento base descargado listo para procesar.")
        except Exception as e:
            print(f"   -> [Aviso] Falló Xray: {e}")

        # FASE 3: ESTRUCTURAS Y SUBTAREAS
        print("\n4. Organizando carpetas y vinculando a Jira...")
        target_path = Path(TARGET_DIR)
        files_hu = [p for p in target_path.iterdir() if p.is_file() and 'hu' in p.name.lower()]
        
        archivos_generados = []
        if files_hu:
            res_proc = await asyncio.gather(*(process_single_file(f) for f in files_hu))
            archivos_generados = [n for n in res_proc if n is not None]

        # FASE 4: NOTIFICACIÓN EMAIL
        archivos_finales = list(set(archivos_generados + [a['filename'] for a in meta if 'hu' in a['filename'].lower()]))
        
        if archivos_generados:
            print(f"\n5. Enviando reporte final de {len(archivos_finales)} archivos...")
            await asyncio.to_thread(enviar_email, archivos_finales, current_issue_key)
        else:
            print("\n5. No se generaron cambios suficientes para enviar correo.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)