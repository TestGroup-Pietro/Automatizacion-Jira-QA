#!/bin/bash
set -e #por si falla un comando digamos que por permisos


# Este script toma la clave de la incidencia como argumento ($1)

# 1. Obtenemos el argumento (La clave de la incidencia, ej: PROY-123)
ISSUE_KEY="$1"

# 2. Definimos la ruta de destino
TARGET_DIR="CP/$ISSUE_KEY"

# 3. Creamos la carpetas ( p asegura que se cree CP si no existe)
mkdir -p "$TARGET_DIR"

echo "Carpeta principal: CP"
echo "Subcarpeta de la incidencia creada: $TARGET_DIR"

# 4. Exportamos la ruta para que GitHub Actions pueda usarla
# ESTA es la parte CLAVE: Escribir en $GITHUB_ENV para que el .yml lo lea.
if [ -n "$GITHUB_ENV" ]; then 
    echo "TARGET_DIR=$TARGET_DIR" >> $GITHUB_ENV # --> puede fallar en local o fuera de Github Actions
fi
# Salida del script (0 indica éxito)
exit 0