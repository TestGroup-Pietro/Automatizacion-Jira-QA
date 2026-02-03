import pandas as pd
from io import StringIO
import uuid
from pathlib import Path
import re # Necesario para la limpieza de texto

def createxlsx(csv_text: str, target_dir: Path, name_issue: str) -> Path:
    """
    Convierte el texto en formato CSV (devuelto por la IA) en un archivo XLSX 
    usando Pandas y XlsxWriter, aplica formato, y lo guarda en el directorio especificado.

    :param csv_text: El string de datos en formato CSV (obtenido de la IA).
    :param target_dir: La ruta (Path object) donde se debe guardar el archivo XLSX.
    :param name_issue: La clave de la incidencia (ej: T1-1).
    :return: La ruta completa del archivo XLSX creado.
    """

    # --- 1. LIMPIEZA Y NORMALIZACIÓN DE DATOS ---
    limpio_text = '\n'.join([line.strip() for line in csv_text.strip().split('\n') if line.strip()])
    limpio_text = limpio_text.replace('"', '') 
    csv_file = StringIO(limpio_text)

    # --- 2. PARSEO DE DATOS (CON PANDAS) ---
    try:
        df = pd.read_csv(
            csv_file, 
            sep=';', 
            header='infer', 
            skipinitialspace=True, 
            lineterminator='\n'
        )
        df.dropna(how='all', inplace=True)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

    except Exception as e:
        print(f"ERROR: Falló el parseo del CSV con Pandas. Revise el formato del string de la IA: {e}")
        raise e 

    # --- 3. CONSTRUCCIÓN DE LA RUTA Y ESCRITURA ---
    unique_id = uuid.uuid4().hex[:8]
    nombre_base = f"CP_{name_issue}_{unique_id}.xlsx"
    ruta_guardado = target_dir / nombre_base 
    
    # 3.2. Definir el motor de escritura (xlsxwriter es requerido para formatear)
    writer = pd.ExcelWriter(ruta_guardado, engine='xlsxwriter')
    
    # 3.3. Escribir los datos en el archivo (¡Rápido y eficiente!)
    # NOTA: Escribimos los datos SIN formato aún
    df.to_excel(writer, sheet_name='Casos de Prueba', index=False, startrow=1, header=False) # startrow=1, header=False
    
    # --- 4. APLICACIÓN DE FORMATO (CON XLSXWRITER) ---
    
    workbook = writer.book
    worksheet = writer.sheets['Casos de Prueba']
    
    # 4.1. Definir el formato del ENCABEZADO (Fila 1)
    verde_claro_hex = '#CCFFCC'
    header_format = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'bg_color': verde_claro_hex,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True
    })

    # 4.2. Definir el formato de los DATOS (Todo el Cuerpo) <--- ¡NUEVO FORMATO!
    data_format = workbook.add_format({
        'align': 'center',       # Alineación horizontal: Centro
        'valign': 'vcenter',     # Alineación vertical: Centro
        'text_wrap': True        # Ajuste de texto (Wrap Text): Activado
    })
    
    # 4.3. Escribir el encabezado y aplicar formato
    for i, col_name in enumerate(df.columns):
        # Escribir el nombre del encabezado en la fila 0 (fila 1 de Excel) con su formato
        worksheet.write(0, i, col_name, header_format) 
        
        # 4.4. Aplicar el formato de datos a TODAS LAS CELDAS DE LA COLUMNA
        # El formato se aplica al rango de filas (desde la fila 1 hasta el final)
        
        # worksheet.set_column(col_inicio, col_fin, ancho, formato)
        # Aplicamos el ancho de columna que ya calculaste:
        max_len = max(
            df[col_name].astype(str).map(len).max(),
            len(col_name)
        ) or 10 
        width = min(max_len * 1.2, 60)
        
        # Aplicamos el ancho y el formato de datos a TODAS LAS CELDAS (excepto el encabezado)
        # El formato se aplicará de la fila 1 hasta la última (1048576, que es el máximo)
        worksheet.set_column(i, i, width, data_format) 

    # --- 5. CIERRE Y RETORNO ---
    
    writer.close()
    
    print(f"Archivo '{nombre_base}' creado exitosamente en: {ruta_guardado}")
    
    return ruta_guardado