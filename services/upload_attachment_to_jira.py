import os
import requests
from pathlib import Path
from requests.auth import HTTPBasicAuth
from typing import Union

def upload_attachment_to_jira(
    file_path: Path, 
    issue_key: str,
    jira_url: str,
    jira_user: str,
    jira_token: str
) -> bool:
    """
    Sube un archivo como adjunto a la incidencia de Jira especificada.

    :param file_path: Ruta del archivo (objeto Path) a subir.
    :param issue_key: Clave de la incidencia (ej: T1-1).
    :param jira_url: URL base de la instancia de Jira (ej: https://tudominio.atlassian.net).
    :param jira_user: Usuario o Email para la autenticación.
    :param jira_token: Token de API para la autenticación.
    :return: True si la subida fue exitosa, False en caso contrario.
    """
    
    # 1. Validación inicial
    if not file_path.exists():
        print(f"ERROR JIRA UPLOAD: El archivo no existe en la ruta: {file_path}")
        return False

    if not all([jira_url, jira_user, jira_token]):
        print("ERROR JIRA UPLOAD: Faltan credenciales de Jira.")
        return False

    # 2. Configuración de la API
    # URL del endpoint de adjuntos: /rest/api/2/issue/{issueKey}/attachments
    upload_url = f"{jira_url.rstrip('/')}/rest/api/2/issue/{issue_key}/attachments"
    auth = HTTPBasicAuth(jira_user, jira_token)
    
    # 3. Preparación de la solicitud
    # Este header es necesario para uploads de adjuntos en Jira Cloud/Server
    headers = {
        "X-Atlassian-Token": "no-check", 
    }

    # Abrir el archivo en modo binario
    with open(file_path, 'rb') as f:
        files = {
            # 'file': (nombre_archivo, contenido_binario, tipo_mime)
            'file': (file_path.name, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        }
        
        print(f"Intentando subir el archivo '{file_path.name}' a la incidencia {issue_key}...")
        
        # 4. Envío de la solicitud POST
        response = requests.post(
            upload_url,
            auth=auth,
            files=files,
            headers=headers
        )

    # 5. Manejo de la respuesta
    if response.status_code == 200:
        print(f"  -> UPLOAD ÉXITOSO: '{file_path.name}' adjuntado a {issue_key}.")
        return True
    else:
        print(f"  -> UPLOAD FALLIDO: Error {response.status_code} al adjuntar '{file_path.name}'.")
        try:
            print(f"     Respuesta de Jira: {response.json()}")
        except requests.exceptions.JSONDecodeError:
            print(f"     Respuesta de Jira (Texto): {response.text}")
        return False