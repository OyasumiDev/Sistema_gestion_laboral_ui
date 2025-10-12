import flet as ft
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.core.interfaces.database_mysql import DatabaseMysql
from app.views.containers.messages import mostrar_mensaje
from datetime import datetime


class DatabaseSettingsArea(ft.Container):
    """
    Centro de respaldo y restauración de datos:
      • Exportar (ZIP JSONL o SQL completo)
      • Importar (ZIP JSONL o SQL completo)
    Limpia y compatible con Flet 0.23 + MySQL 8.0.
    """
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, padding=20)
        self.page = page
        self.db = DatabaseMysql()

        self._setup_invokers()
        self._build_ui()

    # -------------------------- UI --------------------------
    def _build_ui(self):
        title = ft.Text("Respaldo y Restauración de Datos", size=24, weight="bold")

        # --- Exportar ---
        export_title = ft.Text("Exportar", size=18, weight="bold")

        self.btn_export_zip = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Image(src="assets/buttons/save-database-button.png", width=22, height=22),
                    ft.Text("Exportar datos (ZIP JSONL)"),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=self._confirm_export_zip,
        )

        self.btn_export_sql = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Image(src="assets/buttons/save-database-button.png", width=20, height=20),
                    ft.Text("Exportar base completa (SQL)"),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=self._confirm_export_sql,
        )

        export_block = ft.Column(
            controls=[
                export_title,
                ft.Text(
                    "Genera respaldos que puedes guardar en un archivo. "
                    "Usa el ZIP JSONL para datos por modelos y el SQL para un respaldo completo.",
                    size=12,
                    color=ft.colors.GREY_700,
                ),
                ft.Row(
                    [self.btn_export_zip, self.btn_export_sql],
                    spacing=12,
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
            spacing=10,
        )

        # --- Importar ---
        import_title = ft.Text("Importar", size=18, weight="bold")

        self.import_mode_dd = ft.Dropdown(
            label="Modo de importación (ZIP JSONL)",
            options=[
                ft.dropdown.Option("truncate", "Reemplazar todo (TRUNCATE + INSERT)"),
                ft.dropdown.Option("upsert", "Actualizar si existe (UPSERT)"),
                ft.dropdown.Option("insert_ignore", "Insertar ignorando duplicados"),
            ],
            value="upsert",
            width=360,
        )

        self.btn_import_zip = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Image(src="assets/buttons/import_database-button.png", width=22, height=22),
                    ft.Text("Importar datos (ZIP JSONL)"),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=self._confirm_import_zip,
        )

        self.btn_import_sql = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Image(src="assets/buttons/import_database-button.png", width=20, height=20),
                    ft.Text("Importar base completa (SQL)"),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=self._confirm_import_sql,
        )

        import_block = ft.Column(
            controls=[
                import_title,
                ft.Text(
                    "Restaura desde un respaldo. ZIP JSONL respeta dependencias entre tablas y te permite elegir el modo. "
                    "SQL reemplaza toda la base (estructura + datos).",
                    size=12,
                    color=ft.colors.GREY_700,
                ),
                self.import_mode_dd,
                ft.Row(
                    [self.btn_import_zip, self.btn_import_sql],
                    spacing=12,
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
            spacing=10,
        )

        self.content = ft.Column(
            controls=[
                title,
                ft.Divider(height=16),
                export_block,
                ft.Divider(height=24),
                import_block,
            ],
            spacing=14,
        )

    # ---------------------- Invokers ----------------------
    def _setup_invokers(self):
        # Export / Import de DATOS (ZIP JSONL)
        self.invoker_data = FileSaveInvoker(
            page=self.page,
            on_save=self._do_export_data_zip,
            on_import=self._do_import_data_zip,
            save_dialog_title="Guardar datos (ZIP JSONL)",
            import_dialog_title="Selecciona ZIP de datos",
            allowed_extensions=["zip"],
            import_extensions=["zip"],
            file_name="gl_datos_backup.zip",
        )

        # Export / Import de SQL completo
        self.invoker_sql = FileSaveInvoker(
            page=self.page,
            on_save=self._do_export_db_sql,
            on_import=self._do_import_db_sql,
            save_dialog_title="Guardar base completa (SQL)",
            import_dialog_title="Selecciona archivo SQL",
            allowed_extensions=["sql"],
            import_extensions=["sql"],
            file_name="respaldo_gestion_laboral.sql",
        )

    # ---------------------- Confirmaciones ----------------------
    def _open_confirm(self, title: str, bullets: list[str], on_confirm):
        content_col = ft.Column(
            controls=[ft.Text(f"• {b}", size=13) for b in bullets],
            spacing=6,
            tight=True,
        )
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight="bold"),
            content=content_col,
            actions_alignment=ft.MainAxisAlignment.END,
        )

        def _cancel(_): self._close_dialog(dlg)
        def _ok(_): on_confirm(dlg)

        dlg.actions = [
            ft.TextButton("Cancelar", on_click=_cancel),
            ft.ElevatedButton("Entendido, continuar", on_click=_ok),
        ]
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _close_dialog(self, dlg: ft.AlertDialog):
        dlg.open = False
        self.page.update()

    # ---------------------- Exportar ----------------------
    def _confirm_export_zip(self, _e):
        self._open_confirm(
            "Exportar datos (ZIP JSONL)",
            bullets=[
                "Se generará un archivo ZIP con meta.json y un .jsonl por cada tabla.",
                "Incluye únicamente DATOS (no SPs ni vistas).",
            ],
            on_confirm=lambda d: self._proceed_export_zip(d),
        )

    def _proceed_export_zip(self, dlg):
        self._close_dialog(dlg)
        self.invoker_data.open_save()

    def _confirm_export_sql(self, _e):
        self._open_confirm(
            "Exportar base completa (SQL)",
            bullets=[
                "Se generará un archivo .sql con estructura y datos de TODA la base.",
                "Ideal para un respaldo completo compatible con tu versión de MySQL.",
            ],
            on_confirm=lambda d: self._proceed_export_sql(d),
        )

    def _proceed_export_sql(self, dlg):
        self._close_dialog(dlg)
        self.invoker_sql.open_save()

    # ---------------------- Importar ----------------------
    def _confirm_import_zip(self, _e):
        modo = (self.import_mode_dd.value or "upsert").strip()
        explicacion = {
            "truncate": "TRUNCATE + INSERT: borra el contenido de cada tabla y vuelve a insertar todo.",
            "upsert": "UPSERT: inserta y actualiza si ya existe (mantiene datos, actualiza en colisión).",
            "insert_ignore": "INSERT IGNORE: inserta solo lo nuevo y omite duplicados.",
        }.get(modo, "UPSERT por defecto.")
        self._open_confirm(
            "Importar datos (ZIP JSONL)",
            bullets=[
                f"Modo elegido: {explicacion}",
                "Respetará el orden de dependencias (padres → hijos).",
            ],
            on_confirm=lambda d: self._proceed_import_zip(d),
        )

    def _proceed_import_zip(self, dlg):
        self._close_dialog(dlg)
        self.invoker_data.open_import()

    def _confirm_import_sql(self, _e):
        self._open_confirm(
            "Importar base completa (SQL)",
            bullets=[
                "Se REEMPLAZARÁ toda la base de datos (DROP + CREATE + INSERT).",
                "Asegúrate de tener respaldo antes de continuar.",
            ],
            on_confirm=lambda d: self._proceed_import_sql(d),
        )

    def _proceed_import_sql(self, dlg):
        self._close_dialog(dlg)
        self.invoker_sql.open_import()

    # ---------------------- Operaciones reales ----------------------
    def _do_export_data_zip(self, save_path: str):
        try:
            ok = self.db.exportar_datos_zip(save_path)
            if ok:
                mostrar_mensaje(
                    self.page, "✅ Exportación completa",
                    f"Datos exportados correctamente.\nRuta: {save_path}",
                )
            else:
                mostrar_mensaje(self.page, "⚠️ Error", "No se pudo exportar los datos.")
        except Exception as ex:
            mostrar_mensaje(self.page, "❌ Error al exportar", str(ex))

    def _do_import_data_zip(self, import_path: str):
        try:
            modo = (self.import_mode_dd.value or "upsert").strip()
            ok = self.db.importar_datos_zip(import_path, modo=modo)
            if ok:
                mostrar_mensaje(
                    self.page, "✅ Importación exitosa",
                    f"Datos importados correctamente.\nArchivo: {import_path}",
                )
                self.db.connect()
                pubsub = getattr(self.page, "pubsub", None)
                if pubsub:
                    try:
                        if hasattr(pubsub, "publish"):
                            pubsub.publish("db:refrescar_datos", True)
                        elif hasattr(pubsub, "send_all"):
                            try:
                                pubsub.send_all("db:refrescar_datos", True)
                            except TypeError:
                                pubsub.send_all("db:refrescar_datos")
                    except Exception:
                        pass
            else:
                mostrar_mensaje(self.page, "⚠️ Error", "No se pudo importar los datos.")
        except Exception as ex:
            mostrar_mensaje(self.page, "❌ Error crítico", str(ex))

    def _do_export_db_sql(self, path: str):
        try:
            success = self.db.exportar_base_datos(path)
            if success:
                mostrar_mensaje(
                    self.page, "✅ Exportación completa",
                    f"La base fue exportada correctamente.\nRuta: {path}",
                )
            else:
                mostrar_mensaje(self.page, "⚠️ Error", "No se pudo exportar la base.")
        except Exception as e:
            mostrar_mensaje(self.page, "❌ Error al exportar", str(e))

    def _do_import_db_sql(self, path: str):
        try:
            print(f"[DB_LOG] 🚀 Restaurando base desde {path}")
            success = self.db.importar_base_datos(path, page=self.page)

            if success:
                print(f"[DB_LOG] 🔁 Reconectando a base '{self.db.database}' después de restauración...")
                self.db.connect()
                pubsub = getattr(self.page, "pubsub", None)
                if pubsub:
                    try:
                        if hasattr(pubsub, "publish"):
                            pubsub.publish("db:refrescar_datos", True)
                        elif hasattr(pubsub, "send_all"):
                            try:
                                pubsub.send_all("db:refrescar_datos", True)
                            except TypeError:
                                pubsub.send_all("db:refrescar_datos")
                    except Exception:
                        pass
                mostrar_mensaje(
                    self.page, "✅ Importación completa",
                    f"La base de datos '{self.db.database}' fue reconstruida correctamente.\nArchivo: {path}",
                )
            else:
                mostrar_mensaje(self.page, "⚠️ Error", f"No se pudo importar la base '{self.db.database}'.")
        except Exception as e:
            mostrar_mensaje(self.page, "❌ Error", f"Ocurrió un error al restaurar:\n{e}")
