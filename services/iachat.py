import os
from pypdf import PdfReader
from openai import OpenAI

# ******************************************************************
# 1. BASE DEL PROMPT (Ahora como una plantilla sin la variable issue)
# Usamos un marcador de posición, como {issue_code}, en lugar de una f-string
# que se evaluaría de inmediato.
texto_plantilla = """
NECESITO QUE HAGAS LO SIGUIENTE:
ANALIZA LA HISTORIA DE USUARIO PROPORCIONADA A CONTINUACIÓN. IDENTIFICA LOS REQUISITOS CLAVE Y GENERA UNA LISTA DE CASOS DE PRUEBA (TEST CASES) CUBRIENDO ESCENARIOS POSITIVOS, NEGATIVOS Y DE BORDE.
EL FORMATO DE RESPUESTA DEBE SER CSV PURO, UTILIZANDO ÚNICAMENTE EL PUNTO Y COMA (;) COMO DELIMITADOR. NO INCLUIR ENCABEZADOS, INTRODUCCIONES, CONCLUSIONES O CUALQUIER TEXTO ADICIONAL FUERA DEL CONTENIDO CSV.

EL RESULTADO DEBE CONTENER EXACTAMENTE 11 COLUMNAS CON LOS SIGUIENTES CAMPOS (ENCABEZADOS) EN ESTE ORDEN:
1. ID del Caso: Formato numero_correlativo_{issue_code} (Ej: 1_{issue_code}).
2. Módulo/Funcionalidad: Característica específica probada.
3. Descripción/Objetivo: Breve explicación de la validación.
4. Precondiciones: Requisitos previos a la ejecución.
5. Pasos de Ejecución: Acciones detalladas a seguir.
6. Resultado Esperado: La respuesta esperada del sistema.
7. Resultado Actual: Debe contener la palabra RELLENAR.
8. Estado (Status): Debe contener la palabra NO EJECUTADO.
9. ID del Defecto (si aplica): Debe contener la palabra RELLENAR.
10. Fecha de Ejecución: Debe contener la palabra RELLENAR.
11. Recursos: Debe contener la palabra RELLENAR.

LOS CAMPOS DEBEN DE IR EN LA PRIMERA FILA

LA HISTORIA DE USUARIO ES LA SIGUIENTE:

"""

# ******************************************************************
def send_chat(text_doc: str, name_issue: str) -> str:
    try:
        
        # 2. CONSTRUYE EL PROMPT: Inserta el name_issue en la plantilla
        # Usamos .format() o una f-string para reemplazar el marcador {issue_code}
        # y luego concatenamos el texto del documento.
        
        # Primero formateamos la plantilla con el valor de name_issue
        prompt_formateado = texto_plantilla.format(issue_code=name_issue)
        
        # Ahora concatenamos la información completa
        prompt_completo = prompt_formateado + text_doc
        
        # generamos la consulta a chatgpt
        client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key= os.getenv('OPENROUTER_APIKEY'),
        )

        completion = client.chat.completions.create(
        extra_headers={
            "HTTP-Referer": "<YOUR_SITE_URL>",
            "X-Title": "<YOUR_SITE_NAME>",
        },
        extra_body={},
        model="google/gemma-3-4b-it:free",
        messages=[
                    {
                        "role": "user",
                        # Aquí pasamos el prompt completo
                        "content": prompt_completo 
                    }
                ]
        )
        # la respuesta la podemos almacenar en una variable
        csv_text = completion.choices[0].message.content
        return csv_text
        
    except FileNotFoundError:
        # ... (código de manejo de errores omitido por brevedad)
        return ""
