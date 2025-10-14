# app/views/containers/database_settings_area.py
import os
from datetime import datetime
import flet as ft

from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.core.interfaces.database_mysql import DatabaseMysql
from app.views.containers.messages import mostrar_mensaje


class DatabaseSettingsArea(ft.Container):
    """
    Centro de respaldo y restauración de datos (seguro):
      • Exportar (ZIP JSONL o SQL completo)
      • Importar (ZIP JSONL o SQL completo)
      • Limpiar todas las tablas (con opción de respaldo previo)

    Versión sin overlay de carga (no bloquea con modales del sistema).
    """

    def __init__(self, page: ft.Page):
        super().__init__(expand=True, padding=20)

        # Page
        self.page = page

        # Estado "ocupado" (solo para deshabilitar botones; sin overlay)
        self._busy = False

        # Modelo
        self.db = DatabaseMysql()

        # UI
        self._setup_invokers()
        self._build_ui()

    # -------------------------- Helpers seguros --------------------------
    def _get_page(self) -> ft.Page | None:
        return getattr(self, "page", None)

    def _safe_update(self):
        try:
            self.update()
            return
        except Exception:
            pass
        p = self._get_page()
        if p:
            try:
                p.update()
            except Exception:
                pass

    def _close_any_dialog(self):
        """Cierra cualquier diálogo activo para evitar 'modales zombis'."""
        p = self._get_page()
        if not p:
            return
        dlg = getattr(p, "dialog", None)
        if dlg:
            try:
                dlg.open = False
            except Exception:
                pass
            try:
                p.dialog = None
                p.update()
            except Exception:
                pass

    def _set_buttons_enabled(self, enabled: bool):
        for btn in (
            getattr(self, "btn_export_zip", None),
            getattr(self, "btn_export_sql", None),
            getattr(self, "btn_import_zip", None),
            getattr(self, "btn_import_sql", None),
            getattr(self, "btn_clear_data", None),
        ):
            if isinstance(btn, (ft.ElevatedButton, ft.OutlinedButton, ft.FilledButton, ft.TextButton)):
                btn.disabled = not enabled
        self._safe_update()

    # ---- SIN OVERLAY DE CARGA ----
    def _show_busy(self):
        if self._busy:
            return
        self._busy = True
        self._set_buttons_enabled(False)

    def _hide_busy(self):
        if not self._busy:
            return
        self._busy = False
        self._set_buttons_enabled(True)
        self._close_any_dialog()

    def _run_bg(self, target, *args, after=None):
        """
        Ejecuta target en background (si run_thread existe) sin overlay.
        Llama after(resultado, error) al finalizar.
        """
        self._show_busy()
        p = self._get_page()

        def worker(*_ignored_args, **_ignored_kwargs):
            try:
                return (target(*args), None)
            except Exception as e:
                return (None, e)

        def on_done(res):
            try:
                if isinstance(res, tuple) and len(res) == 2 and (
                    res[1] is None or isinstance(res[1], BaseException)
                ):
                    result, error = res
                else:
                    result, error = res, None
            except Exception as e:
                result, error = None, e
            finally:
                self._hide_busy()

            if callable(after):
                try:
                    after(result, error)
                except Exception:
                    pass

        if p and hasattr(p, "run_thread"):
            p.run_thread(worker, on_done)
        else:
            result, error = worker()
            self._hide_busy()
            if callable(after):
                try:
                    after(result, error)
                except Exception:
                    pass

    # ------ Invokers: asegurar siempre la Page antes de abrir diálogos ------
    def _ensure_invoker_page(self, invoker: FileSaveInvoker):
        """Se asegura de que el invoker tenga una Page válida antes de abrir file pickers."""
        p = self._get_page()
        try:
            # Reinyecta siempre por si el invoker perdió la referencia
            invoker.page = p
        except Exception:
            pass
        return p

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

        # --- Limpiar datos ---
        cleanup_title = ft.Text("Mantenimiento", size=18, weight="bold")
        self.btn_clear_data = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Image(src="assets/buttons/trash-bin.png", width=22, height=22),
                    ft.Text("Borrar todos los datos del programa"),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            style=ft.ButtonStyle(color=ft.colors.RED_400),
            on_click=self.borrar_datos_programa,
        )

        cleanup_block = ft.Column(
            controls=[
                cleanup_title,
                ft.Text(
                    "Permite limpiar completamente las tablas del sistema. "
                    "Se recomienda guardar un respaldo antes de hacerlo.",
                    size=12,
                    color=ft.colors.GREY_700,
                ),
                self.btn_clear_data,
            ],
            spacing=10,
        )

        # --- Contenedor principal ---
        self.content = ft.Column(
            controls=[
                title,
                ft.Divider(height=16),
                export_block,
                ft.Divider(height=24),
                import_block,
                ft.Divider(height=24),
                cleanup_block,
            ],
            spacing=14,
        )

    # ---------------------- Invokers ----------------------
    def _setup_invokers(self):
        # Export / Import ZIP JSONL
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

        # Export / Import SQL completo
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
        # Cierra lo que esté abierto antes de abrir otro diálogo
        self._close_any_dialog()

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

        def _cancel(_):
            self._close_dialog(dlg)

        def _ok(_):
            self._close_dialog(dlg)
            on_confirm(dlg)

        dlg.actions = [
            ft.TextButton("Cancelar", on_click=_cancel),
            ft.ElevatedButton("Entendido, continuar", on_click=_ok),
        ]

        p = self._get_page()
        if p:
            p.dialog = dlg
            dlg.open = True
            try:
                p.update()
            except Exception:
                pass

    def _close_dialog(self, dlg: ft.AlertDialog):
        p = self._get_page()
        try:
            dlg.open = False
        except Exception:
            pass
        if p:
            try:
                if getattr(p, "dialog", None) is dlg:
                    p.dialog = None
                p.update()
            except Exception:
                pass

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
        self._ensure_invoker_page(self.invoker_data)
        try:
            self.invoker_data.open_save()
        except Exception as e:
            mostrar_mensaje(self.page, "❌ No se pudo abrir el diálogo de guardado", str(e))

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
        self._ensure_invoker_page(self.invoker_sql)
        try:
            self.invoker_sql.open_save()
        except Exception as e:
            mostrar_mensaje(self.page, "❌ No se pudo abrir el diálogo de guardado", str(e))

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
        self._ensure_invoker_page(self.invoker_data)
        try:
            self.invoker_data.open_import()
        except Exception as e:
            mostrar_mensaje(self.page, "❌ No se pudo abrir el diálogo de importación", str(e))

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
        self._ensure_invoker_page(self.invoker_sql)
        try:
            self.invoker_sql.open_import()
        except Exception as e:
            mostrar_mensaje(self.page, "❌ No se pudo abrir el diálogo de importación", str(e))

    # ---------------------- Validadores de rutas ----------------------
    @staticmethod
    def _ensure_ext(path: str, ext: str) -> str:
        ext = ext.lower().lstrip(".")
        if not path.lower().endswith("." + ext):
            return f"{path}.{ext}"
        return path

    @staticmethod
    def _check_allowed(path: str, allowed_exts: list[str]) -> bool:
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        return ext in [e.lower().lstrip(".") for e in allowed_exts]

    # ---------------------- Operaciones reales (ZIP JSONL) ----------------------
    def _do_export_data_zip(self, save_path: str):
        save_path = self._ensure_ext((save_path or "").strip(), "zip")

        def work():
            return self.db.exportar_datos_zip(save_path)

        def done(result, error):
            self._close_any_dialog()
            if error:
                mostrar_mensaje(self.page, "❌ Error al exportar", str(error))
                return
            if result:
                mostrar_mensaje(self.page, "✅ Exportación completa",
                                f"Datos exportados correctamente.\nRuta: {save_path}")
            else:
                mostrar_mensaje(self.page, "⚠️ Error", "No se pudo exportar los datos.")

        self._run_bg(work, after=done)

    def _do_import_data_zip(self, import_path: str):
        import_path = (import_path or "").strip()
        if not import_path or not os.path.exists(import_path):
            self._close_any_dialog()
            mostrar_mensaje(self.page, "⚠️ Archivo no válido", "Selecciona un ZIP válido para importar.")
            return
        if not self._check_allowed(import_path, ["zip"]):
            self._close_any_dialog()
            mostrar_mensaje(self.page, "⚠️ Extensión inválida", "Debe ser un archivo .zip")
            return

        modo = (self.import_mode_dd.value or "upsert").strip()

        def work():
            return self.db.importar_datos_zip(import_path, modo=modo)

        def done(result, error):
            self._close_any_dialog()
            if error:
                mostrar_mensaje(self.page, "❌ Error crítico", str(error))
                return
            if result:
                mostrar_mensaje(self.page, "✅ Importación exitosa",
                                f"Datos importados correctamente.\nArchivo: {import_path}")
                try:
                    self.db.connect()
                except Exception:
                    pass
                pubsub = getattr(self.page, "pubsub", None)
                if pubsub:
                    try:
                        if hasattr(pubsub, "publish"):
                            pubsub.publish("db:refrescar_datos", True)
                        elif hasattr(pubsub, "send_all"):
                            pubsub.send_all("db:refrescar_datos", True)
                    except Exception:
                        pass
            else:
                mostrar_mensaje(self.page, "⚠️ Error", "No se pudo importar los datos.")

        self._run_bg(work, after=done)

    # ---------------------- Operaciones reales (SQL completo) ----------------------
    def _do_export_db_sql(self, path: str):
        path = self._ensure_ext((path or "").strip(), "sql")

        def work():
            return self.db.exportar_base_datos(path)

        def done(result, error):
            self._close_any_dialog()
            if error:
                mostrar_mensaje(self.page, "❌ Error al exportar", str(error))
                return
            if result:
                mostrar_mensaje(self.page, "✅ Exportación completa",
                                f"La base fue exportada correctamente.\nRuta: {path}")
            else:
                mostrar_mensaje(self.page, "⚠️ Error", "No se pudo exportar la base.")

        self._run_bg(work, after=done)

    def _do_import_db_sql(self, path: str):
        path = (path or "").strip()
        if not path or not os.path.exists(path):
            self._close_any_dialog()
            mostrar_mensaje(self.page, "⚠️ Archivo no válido", "Selecciona un .sql válido para importar.")
            return
        if not self._check_allowed(path, ["sql"]):
            self._close_any_dialog()
            mostrar_mensaje(self.page, "⚠️ Extensión inválida", "Debe ser un archivo .sql")
            return

        def work():
            return self.db.importar_base_datos(path, page=self.page)

        def done(result, error):
            self._close_any_dialog()
            if error:
                mostrar_mensaje(self.page, "❌ Error", f"Ocurrió un error al restaurar:\n{error}")
                return
            if result:
                try:
                    self.db.connect()
                except Exception:
                    pass
                mostrar_mensaje(
                    self.page, "✅ Importación completa",
                    f"La base de datos '{self.db.database}' fue reconstruida correctamente.\nArchivo: {path}"
                )
            else:
                mostrar_mensaje(self.page, "⚠️ Error", f"No se pudo importar la base '{self.db.database}'.")

        self._run_bg(work, after=done)

    # ---------------------- Borrar datos del programa ----------------------
    def borrar_datos_programa(self, _e=None):
        self._close_any_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("🧹 Limpiar todos los datos del programa", weight="bold"),
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Esta acción eliminará TODO el contenido de las tablas del sistema.",
                        size=13, color=ft.colors.RED_400
                    ),
                    ft.Text(
                        "⚠️ Es recomendable hacer un respaldo antes de continuar.",
                        size=12, italic=True, color=ft.colors.GREY_700
                    ),
                    ft.Text(
                        "Puedes guardar tus datos actuales (ZIP JSONL) antes de limpiar o "
                        "borrar directamente. Esta acción no puede deshacerse.",
                        size=12, color=ft.colors.GREY_700
                    ),
                ],
                spacing=8, tight=True
            ),
            actions_alignment=ft.MainAxisAlignment.END,
        )

        def _cancel(_):
            self._close_dialog(dlg)

        def _borrar_sin_guardar(_):
            self._close_dialog(dlg)
            self._proceed_clear_tables()

        def _guardar_y_borrar(_):
            self._close_dialog(dlg)
            fecha = datetime.today().strftime("%Y%m%d_%H%M%S")
            nombre = f"respaldo_pre_borrado_{fecha}.zip"
            self.invoker_data = FileSaveInvoker(
                page=self.page,
                on_save=lambda path: self._export_y_luego_limpiar(path),
                save_dialog_title="Guardar respaldo antes de limpiar",
                allowed_extensions=["zip"],
                file_name=nombre,
            )
            self._ensure_invoker_page(self.invoker_data)
            try:
                self.invoker_data.open_save()
            except Exception as e:
                mostrar_mensaje(self.page, "❌ No se pudo abrir el diálogo de guardado", str(e))

        dlg.actions = [
            ft.TextButton("Cancelar", on_click=_cancel),
            ft.TextButton(
                "Borrar sin guardar",
                on_click=_borrar_sin_guardar,
                style=ft.ButtonStyle(color=ft.colors.RED_400)
            ),
            ft.ElevatedButton("Guardar y limpiar", on_click=_guardar_y_borrar),
        ]
        p = self._get_page()
        if p:
            p.dialog = dlg
            dlg.open = True
            try:
                p.update()
            except Exception:
                pass

    # ---------------------- Operaciones internas ----------------------
    def _export_y_luego_limpiar(self, path: str):
        path = self._ensure_ext((path or "").strip(), "zip")

        def work():
            return self.db.exportar_datos_zip(path)

        def done(result, error):
            self._close_any_dialog()
            if error or not result:
                mostrar_mensaje(
                    self.page, "⚠️ Error",
                    f"No se pudo crear el respaldo antes de limpiar.\n{error or ''}".strip()
                )
                return
            mostrar_mensaje(self.page, "✅ Respaldo guardado", f"Archivo guardado en:\n{path}")
            self._proceed_clear_tables()

        self._run_bg(work, after=done)

    def _proceed_clear_tables(self):
        def work():
            return self.db.clear_tables()

        def done(result, error):
            self._close_any_dialog()
            if error:
                mostrar_mensaje(self.page, "❌ Error crítico", str(error))
                return
            if result:
                mostrar_mensaje(
                    self.page, "✅ Limpieza completada",
                    f"Todas las tablas de '{self.db.database}' fueron limpiadas correctamente."
                )
                pubsub = getattr(self.page, "pubsub", None)
                if pubsub:
                    try:
                        if hasattr(pubsub, "publish"):
                            pubsub.publish("db:refrescar_datos", True)
                        elif hasattr(pubsub, "send_all"):
                            pubsub.send_all("db:refrescar_datos", True)
                    except Exception:
                        pass
            else:
                mostrar_mensaje(self.page, "⚠️ Error", "No se pudo limpiar las tablas.")

        self._run_bg(work, after=done)
