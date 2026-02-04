import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
import os

# --- CONFIGURACIÓN NECESARIA ---

# 1. Tu dirección de Gmail (usa variables de entorno o configura de forma segura)
SENDER_EMAIL = os.getenv('EMAIL_SENDER') #"tu_correo_de_gmail@gmail.com"

# 2. La contraseña de aplicación (IMPORTANTE: NO USAR CONTRASEÑA NORMAL)
SENDER_PASSWORD = os.getenv('PASSWORD_SENDER') #"tu_contraseña_de_aplicacion"

# 3. El destinatario
RECEIVER_EMAIL = SENDER_EMAIL #"correo_destino@ejemplo.com"


# --- FUNCIÓN DE ENVÍO CORREGIDA ---

def enviar_email(file_list: List[str], name_issue: str):
    """
    Envía un email con la lista de nombres de archivos en el cuerpo del mensaje.
    """
    
    # 1. CONSTRUIR LA LISTA HTML DINÁMICAMENTE
    # Genera <li><strong>nombre_archivo</strong></li> para cada archivo
    list_items = "".join([f"<li><strong>{filename}</strong></li>" for filename in file_list])
    
    # 2. CONFIGURACIÓN DEL MENSAJE
    print("Enviando CORREO de cierre...")
    SUBJECT = f"Proceso Finalizado | Ticket: {os.getenv('JIRA_ISSUE_KEY', 'Desconocido')}"
    
    BODY = f"""
        <h1 style='color:#1E90FF;'>Proceso de Adjuntos de JIRA Finalizado</h1><hr>
        <h3 style='color:#3CB371;'>El ticket {name_issue} en JIRA se actualizo con los siguientes archivos:</h3>
        <ul>
            {list_items}
        </ul>
        <p>Este email confirma que los archivos y carpetas generados han sido subidos a la tarjeta de JIRA.</p>
        """
    
    # Crea el objeto MIME para el mensaje
    mensaje = MIMEMultipart()
    mensaje["From"] = SENDER_EMAIL
    mensaje["To"] = RECEIVER_EMAIL
    mensaje["Subject"] = SUBJECT
    
    # Adjunta el cuerpo del mensaje como HTML
    mensaje.attach(MIMEText(BODY, "html"))
    
    try:
        # 1. Establece la conexión con el servidor SMTP de Gmail (puerto 587 para TLS)
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        
        # 2. Inicia sesión
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        # 3. Envía el correo
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, mensaje.as_string())
        
        print("-> Correo enviado exitosamente.")
        return True # Se añade un retorno para confirmar el éxito

    except Exception as e:
        print(f"-> Error al enviar el correo: {e}")
        return False
        
    finally:
        # Cierra la conexión
        if 'server' in locals():
            server.quit()

