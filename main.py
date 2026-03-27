#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import flet as ft
import sqlite3
import os
import urllib.parse
from datetime import datetime
from typing import List, Dict

# === PARCHE DE SEGURIDAD PARA ANDROID (IMPORTANTE) ===
# Definimos dónde guardar la base de datos de forma segura
if os.environ.get("FLET_PLATFORM") == "android":
    # En Android, usamos la carpeta de documentos privados de la app
    RUTA_APP_DATOS = os.environ.get("FLET_APP_DATA_DIR", "/data/data/com.example.mundodron/files")
    DB_FILENAME = os.path.join(RUTA_APP_DATOS, "mi_base.db")
else:
    # En Termux/Web, seguimos como antes
    DB_FILENAME = "mi_base.db"
# ======================================================

class Config:
    APP_NAME = "Mundo Dron v9.4 (Fix Gris)"
    DB_PATH = DB_FILENAME # Usamos la ruta segura calculada arriba
    BACKUP_DIR = "backups"
    EXPORT_DIR = "exports"

# --- El resto del código de la clase DBManager y main() sigue IGUAL ---
# (Solo asegúrate de no duplicar los imports de arriba)
