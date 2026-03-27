#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import flet as ft
import sqlite3
import os
import urllib.parse
from datetime import datetime
from typing import List, Dict

class Config:
    APP_NAME = "Mundo Dron v9.3 (APK Ready)"
    DB_PATH = "mi_base.db"
    BACKUP_DIR = "backups"
    EXPORT_DIR = "exports"

class DBManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._migrate()
    
    def _connect(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
    
    def _column_exists(self, table: str, column: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        return any(col[1] == column for col in cursor.fetchall())
    
    def _migrate(self):
        cursor = self.conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS Categorias (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE, activo INTEGER DEFAULT 1)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS Registros (id INTEGER PRIMARY KEY AUTOINCREMENT, categoria_id INTEGER NOT NULL, titulo TEXT NOT NULL, descripcion TEXT, creado_en DATETIME DEFAULT CURRENT_TIMESTAMP, eliminado INTEGER DEFAULT 0, cantidad INTEGER DEFAULT 1)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS Notas (id INTEGER PRIMARY KEY AUTOINCREMENT, contenido TEXT NOT NULL, fecha DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        
        if not self._column_exists("Categorias", "activo"):
            cursor.execute("ALTER TABLE Categorias ADD COLUMN activo INTEGER DEFAULT 1")
        if not self._column_exists("Registros", "eliminado"):
            cursor.execute("ALTER TABLE Registros ADD COLUMN eliminado INTEGER DEFAULT 0")
        if not self._column_exists("Registros", "cantidad"):
            cursor.execute("ALTER TABLE Registros ADD COLUMN cantidad INTEGER DEFAULT 1")
            
        cursor.execute("SELECT COUNT(*) FROM Categorias")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("INSERT INTO Categorias (nombre) VALUES (?)", [("Mundo Dron",),("Repuestos",),("Baterías",),("Tornillería",),("Herramientas",)])
        self.conn.commit()
    
    def get_stats(self) -> Dict:
        c = self.conn.cursor()
        stats = {}
        c.execute("SELECT COUNT(*) FROM Categorias WHERE activo=1"); stats['categorias'] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM Registros WHERE eliminado=0"); stats['registros'] = c.fetchone()[0]
        return stats
    
    def borrar_registro(self, reg_id: int):
        self.conn.execute("UPDATE Registros SET eliminado=1 WHERE id=?", (reg_id,))
        self.conn.commit()
        
    def borrar_categoria(self, cat_id: int):
        self.conn.execute("UPDATE Categorias SET activo=0 WHERE id=?", (cat_id,))
        self.conn.commit()
        
    def close(self):
        self.conn.commit()
        self.conn.close()

def main(page: ft.Page):
    page.title = Config.APP_NAME
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = "adaptive"
    page.padding = 0
    
    db = DBManager(Config.DB_PATH)
    cuerpo = ft.Container(expand=True)
    
    ruta_base = os.getcwd()
    os.makedirs(os.path.join(ruta_base, Config.BACKUP_DIR), exist_ok=True)
    os.makedirs(os.path.join(ruta_base, Config.EXPORT_DIR), exist_ok=True)
    
    def mostrar_alerta(titulo, mensaje):
        dlg = ft.AlertDialog(title=ft.Text(titulo), content=ft.Text(mensaje))
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def snackbar(msg: str, color="green700"):
        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
        page.snack_bar.open = True
        page.update()
        
    # --- LA IMPRESORA CORREGIDA (Sin UrlLauncher, pero con await) ---
    async def imprimir_rawbt(texto):
        try:
            texto_codificado = urllib.parse.quote(texto)
            enlace = f"rawbt:{texto_codificado}"
            await page.launch_url(enlace)
            snackbar("🖨️ Procesando ticket...", color="blue700")
        except Exception as e:
            mostrar_alerta("Error Impresora", str(e))
    # ----------------------------------------------------------------
    
    # === PANTALLA 1: DASHBOARD NATIVO ===
    def vista_dashboard():
        stats = db.get_stats()
        lista_recientes = ft.Column(spacing=10)
        cursor = db.conn.cursor()
        cursor.execute("""SELECT r.titulo, r.cantidad, c.nombre FROM Registros r 
                          JOIN Categorias c ON r.categoria_id = c.id 
                          WHERE r.eliminado=0 ORDER BY r.id DESC LIMIT 5""")
        for tit, cant, cat in cursor.fetchall():
            lista_recientes.controls.append(
                ft.Card(
                    content=ft.ListTile(
                        leading=ft.Icon(ft.Icons.HISTORY, color="grey"),
                        title=ft.Text(tit, weight="bold"),
                        subtitle=ft.Text(f"Carpeta: {cat}"),
                        trailing=ft.Text(f"x{cant}", size=16, weight="bold", color="blue")
                    ),
                    elevation=2
                )
            )

        return ft.Container(
            content=ft.Column([
                ft.Text("📊 Resumen del Taller", size=24, weight="bold"),
                ft.Row([
                    ft.Container(content=ft.Column([ft.Icon(ft.Icons.FOLDER, size=30), ft.Text(str(stats['categorias']), size=24, weight="bold"), ft.Text("Carpetas")]), padding=15, bgcolor="blue900", border_radius=10, expand=1),
                    ft.Container(content=ft.Column([ft.Icon(ft.Icons.INVENTORY_2, size=30), ft.Text(str(stats['registros']), size=24, weight="bold"), ft.Text("Artículos")]), padding=15, bgcolor="green900", border_radius=10, expand=1),
                ]),
                ft.Divider(),
                ft.Text("Últimos Movimientos", size=18, weight="bold"),
                lista_recientes if lista_recientes.controls else ft.Text("No hay registros aún.", color="grey")
            ], scroll="adaptive", expand=True),
            padding=20, expand=True
        )

    # === PANTALLA 2: INVENTARIO (CARPETAS CON BORRADO SEGURO) ===
    def vista_inventario():
        lista_cats = ft.Column(scroll="adaptive", expand=True)
        cursor = db.conn.cursor()
        cursor.execute("SELECT id, nombre FROM Categorias WHERE activo=1")
        for cid, cnom in cursor.fetchall():
            cursor.execute("SELECT COUNT(*) FROM Registros WHERE categoria_id=? AND eliminado=0", (cid,))
            total_items = cursor.fetchone()[0]
            
            def confirmar_borrado_cat(e, id_borrar=cid, nombre_borrar=cnom):
                def ejecutar_borrado(e2):
                    db.borrar_categoria(id_borrar)
                    dlg.open = False
                    snackbar(f"🗑️ Carpeta '{nombre_borrar}' eliminada")
                    cambiar_vista(1) 
                
                def cancelar_borrado(e2):
                    dlg.open = False
                    page.update()

                dlg = ft.AlertDialog(
                    title=ft.Text("⚠️ Borrar Carpeta"),
                    content=ft.Text(f"¿Estás seguro de borrar '{nombre_borrar}'?\nNo se borrarán los artículos de la base de datos, pero la carpeta desaparecerá de aquí."),
                    actions=[
                        ft.TextButton("Cancelar", on_click=cancelar_borrado),
                        ft.TextButton("Sí, Borrar", on_click=ejecutar_borrado, style=ft.ButtonStyle(color="red"))
                    ]
                )
                page.overlay.append(dlg)
                dlg.open = True
                page.update()
            
            lista_cats.controls.append(
                ft.Card(
                    content=ft.ListTile(
                        title=ft.Text(cnom, weight="bold", size=18),
                        subtitle=ft.Text(f"{total_items} artículos guardados"),
                        leading=ft.Icon(ft.Icons.FOLDER, color="amber400", size=35),
                        on_click=lambda e, i=cid, n=cnom: abrir_categoria(i, n),
                        trailing=ft.IconButton(ft.Icons.DELETE_FOREVER, icon_color="red", on_click=confirmar_borrado_cat)
                    ),
                    elevation=3
                )
            )

        in_nueva_cat = ft.TextField(label="Crear nueva carpeta", expand=True)
        def btn_crear_cat(e):
            if in_nueva_cat.value:
                db.conn.execute("INSERT INTO Categorias (nombre) VALUES (?)", (in_nueva_cat.value,))
                db.conn.commit()
                in_nueva_cat.value = ""
                cambiar_vista(1)

        return ft.Container(content=ft.Column([
            ft.Row([in_nueva_cat, ft.IconButton(ft.Icons.ADD_BOX, on_click=btn_crear_cat, icon_color="green", icon_size=45)]),
            ft.Divider(),
            lista_cats
        ], expand=True), padding=15, expand=True)

    # === SUB-PANTALLA: EDITOR CON ARSENAL DE PLANTILLAS ===
    def abrir_categoria(cat_id, cat_nombre):
        in_titulo = ft.TextField(label="¿Qué guardamos?", expand=True, autofocus=True)
        in_cant = ft.TextField(label="Stock", value="1", width=80, keyboard_type=ft.KeyboardType.NUMBER)
        in_desc = ft.TextField(label="Notas / Formato", multiline=True, min_lines=5)
        
        plantillas = {
            "Ninguna": "",
            "🚁 Checklist Pre-Vuelo": "[ ] Hélices aseguradas\n[ ] Batería al 100%\n[ ] Calibración Brújula\n[ ] Señal GPS > 10 sats\n[ ] SD insertada\n\nFirma/Check: ",
            "🔧 Recepción de Equipo": "Cliente: \nTeléfono: \nModelo: \nNº Serie: \n\nMotivo de entrada:\n- \n\nEstado visual:\n- ",
            "📋 Diagnóstico Técnico": "Problema reportado: \n\nFallo encontrado: \n- \n\nSolución propuesta: \n- \n\nTiempo estimado: ",
            "🔋 Ficha de Batería": "ID Batería: \nCiclos actuales: \nVoltaje Celda 1: \nVoltaje Celda 2: \nVoltaje Celda 3: \nVoltaje Celda 4: \nHinchada: [Sí/No]\nEstado de Salud: %",
            "💰 Presupuesto Formal": "Descripción del servicio:\n1. \n2. \n\nRepuestos: €\nMano de obra: €\n-------------------\nTOTAL PREVISTO: €\n\nValidez: 15 días.",
            "📦 Control de Stock": "Albarán Nº: \nProveedor: \nFecha recepción: \n\nArtículos recibidos:\n- \n- \n\nVerificado por: ",
            "🤝 Préstamo Herramienta": "Herramienta: \nEntregada a: \nFecha entrega: \nFecha devolución prevista: \n\nEstado al entregar: ",
            "🚀 Informe de Vuelo (Log)": "Lugar: \nCondiciones (viento/clima): \nDuración: min\nIncidencias: Ninguna\n\nNotas adicionales: ",
            "❌ Informe de Daños (Crash)": "Fecha del accidente: \nAltitud aprox: \nCausa probable: \n\nDaños estructurales:\n- \nElectrónica afectada:\n- "
        }
        
        dropdown_plantillas = ft.Dropdown(
            label="Insertar Plantilla Profesional",
            options=[ft.dropdown.Option(k) for k in plantillas.keys()],
            value="Ninguna",
            expand=True,
            bgcolor="surfaceVariant"
        )
        
        def aplicar_plantilla(e):
            if dropdown_plantillas.value != "Ninguna":
                texto_actual = in_desc.value if in_desc.value else ""
                in_desc.value = texto_actual + ("\n\n" if texto_actual else "") + plantillas[dropdown_plantillas.value]
                dropdown_plantillas.value = "Ninguna"
                page.update()

        dropdown_plantillas.on_change = aplicar_plantilla

        async def btn_guardar_solo(e):
            await ejecutar_logica_guardado(False)

        async def btn_guardar_e_imprimir(e):
            await ejecutar_logica_guardado(True)

        async def ejecutar_logica_guardado(imprimir_ticket):
            if not in_titulo.value:
                snackbar("❌ Título vacío", color="red")
                return
            try: cantidad = int(in_cant.value)
            except: cantidad = 1

            db.conn.execute("INSERT INTO Registros (categoria_id, titulo, descripcion, cantidad) VALUES (?, ?, ?, ?)", 
                           (cat_id, in_titulo.value, in_desc.value, cantidad))
            db.conn.commit()
            
            if imprimir_ticket:
                ticket = f"=== {cat_nombre.upper()} ===\nItem: {in_titulo.value}\nCant: {cantidad}\n\n-- DETALLES --\n{in_desc.value}\n\n\n"
                await imprimir_rawbt(ticket)
            else:
                snackbar("✅ Guardado en base de datos")
            abrir_categoria(cat_id, cat_nombre)
                
        lista_items = ft.Column(scroll="adaptive", expand=True)
        cursor = db.conn.cursor()
        cursor.execute("SELECT id, titulo, descripcion, cantidad FROM Registros WHERE categoria_id=? AND eliminado=0 ORDER BY id DESC", (cat_id,))
        for rid, tit, desc, cant in cursor.fetchall():
            desc_seg = desc or ""
            
            def borrar(e, id_borrar=rid):
                db.borrar_registro(id_borrar)
                snackbar("🗑️ Borrado")
                abrir_categoria(cat_id, cat_nombre)
                
            async def re_imprimir(e, t=tit, c=cant, d=desc_seg):
                ticket = f"=== {cat_nombre.upper()} ===\nItem: {t}\nCant: {c}\n\n-- DETALLES --\n{d}\n\n\n"
                await imprimir_rawbt(ticket)

            lista_items.controls.append(
                ft.Card(
                    content=ft.ListTile(
                        title=ft.Text(f"{tit} (x{cant})", weight="bold"),
                        subtitle=ft.Text(desc_seg[:50] + "..." if len(desc_seg)>50 else desc_seg),
                        leading=ft.Icon(ft.Icons.CHECK_BOX, color="blue"),
                        trailing=ft.Row([
                            ft.IconButton(icon=ft.Icons.PRINT, icon_color="blue", on_click=re_imprimir),
                            ft.IconButton(icon=ft.Icons.DELETE, icon_color="red", on_click=borrar)
                        ], tight=True)
                    ),
                    elevation=1
                )
            )

        cuerpo.content = ft.Column([
            ft.AppBar(leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: cambiar_vista(1)), title=ft.Text(f"📂 {cat_nombre}"), bgcolor="surfaceVariant"),
            ft.Container(content=ft.Column([
                ft.Row([in_titulo, in_cant]),
                dropdown_plantillas,
                in_desc,
                ft.Row([
                    ft.FilledButton("💾 Solo Guardar", on_click=btn_guardar_solo, expand=True, bgcolor="green700"),
                    ft.FilledButton("🖨️ Guardar e Imprimir", on_click=btn_guardar_e_imprimir, expand=True, bgcolor="blue700")
                ]),
                ft.Divider(),
                lista_items
            ], scroll="adaptive", expand=True), padding=10, expand=True)
        ], expand=True)
        page.update()

    # === PANTALLA 3: HERRAMIENTAS BLINDADAS ===
    def vista_herramientas():
        in_nota = ft.TextField(label="📝 Nota rápida...", multiline=True, min_lines=2)
        async def guardar_nota(e):
            if in_nota.value:
                db.conn.execute("INSERT INTO Notas (contenido) VALUES (?)", (in_nota.value,))
                db.conn.commit()
                ticket = f"-- NOTA --\n{in_nota.value}\n----------\n\n\n"
                await imprimir_rawbt(ticket)
                in_nota.value = ""
                page.update()

        in_texto = ft.TextField(label="☢️ Texto a ofuscar")
        async def pervertir(e):
            if in_texto.value:
                ofuscado = in_texto.value.upper().replace('A','4').replace('E','3').replace('I','1').replace('O','0').replace('S','5').replace('T','7')
                ticket = f"!! SECRET !!\n{ofuscado}\n!!!!!!!!!!!!\n\n\n"
                await imprimir_rawbt(ticket)
                in_texto.value = ""
                page.update()

        def ejecutar_backup(e):
            try:
                import shutil
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                origen = os.path.join(ruta_base, Config.DB_PATH)
                destino = os.path.join(ruta_base, Config.BACKUP_DIR, f"backup_{timestamp}.db")
                shutil.copy(origen, destino)
                mostrar_alerta("Backup Exitoso", f"Archivo guardado en:\n{destino}")
            except Exception as ex:
                mostrar_alerta("Error Crítico", f"No se pudo copiar: {ex}\n\nRuta: {ruta_base}")

        def ejecutar_csv(e):
            try:
                cursor = db.conn.cursor()
                cursor.execute("""SELECT r.id, c.nombre, r.titulo, r.cantidad, r.descripcion, r.creado_en 
                                  FROM Registros r LEFT JOIN Categorias c ON r.categoria_id = c.id 
                                  WHERE r.eliminado=0""")
                regs = cursor.fetchall()
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(ruta_base, Config.EXPORT_DIR, f"inventario_{timestamp}.csv")
                
                with open(path, 'w', encoding='utf-8') as f:
                    f.write("ID,Categoria,Titulo,Cantidad,Descripcion,Fecha\n")
                    for r in regs:
                        cat = r[1] or "SinCat"
                        tit = r[2].replace(',', ' ') if r[2] else ""
                        cant = r[3]
                        desc = (r[4] or "").replace('\n', ' ').replace(',', ' ')
                        f.write(f"{r[0]},{cat},{tit},{cant},{desc},{r[5]}\n")
                
                mostrar_alerta("CSV Creado", f"Excel generado en:\n{path}")
            except Exception as ex:
                mostrar_alerta("Error Crítico", f"No se pudo crear CSV: {ex}\n\nRuta: {ruta_base}")

        return ft.Container(
            content=ft.Column([
                ft.Text("🛠️ Utilidades del Taller", size=24, weight="bold"),
                ft.Divider(),
                in_nota,
                ft.FilledButton("Imprimir Nota", on_click=guardar_nota, icon=ft.Icons.PRINT),
                ft.Divider(),
                in_texto,
                ft.FilledButton("Ofuscar e Imprimir", on_click=pervertir, icon=ft.Icons.SECURITY, bgcolor="red900"),
                ft.Divider(),
                ft.Text("Datos y Backups", weight="bold"),
                ft.Row([
                    ft.FilledButton("Backup DB", on_click=ejecutar_backup, icon=ft.Icons.BACKUP),
                    ft.FilledButton("Exportar CSV", on_click=ejecutar_csv, icon=ft.Icons.TABLE_CHART, bgcolor="orange800")
                ], wrap=True)
            ], scroll="adaptive", expand=True),
            padding=20, expand=True
        )
    
    # === NAVEGACIÓN PRINCIPAL ===
    nav_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.DASHBOARD, label="Inicio"),
            ft.NavigationBarDestination(icon=ft.Icons.FOLDER, label="Carpetas"),
            ft.NavigationBarDestination(icon=ft.Icons.CONSTRUCTION, label="Tools"),
        ],
        on_change=lambda e: cambiar_vista(e.control.selected_index)
    )
    
    def cambiar_vista(idx):
        if idx == 0: cuerpo.content = vista_dashboard()
        elif idx == 1: cuerpo.content = vista_inventario()
        elif idx == 2: cuerpo.content = vista_herramientas()
        page.update()
    
    cuerpo.content = vista_dashboard()
    
    page.add(
        ft.AppBar(title=ft.Text(Config.APP_NAME), bgcolor="black"), 
        cuerpo, 
        nav_bar
    )

if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8564)
