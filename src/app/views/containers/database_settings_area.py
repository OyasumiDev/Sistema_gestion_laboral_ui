# app/views/containers/database_settings_area.py

import flet as ft
from app.core.app_state import AppState
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.core.interfaces.database_mysql import DatabaseMysql
from app.views.containers.messages import mostrar_mensaje

class DatabaseSettingsArea(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, padding=20)
        self.page = page  # Este sí es el que viene de Flet, no del AppState
        self.db = DatabaseMysql()
        self._setup_invoker()
        self._build_ui()

    def _build_ui(self):
        self.content = ft.Column(
            controls=[
                ft.Text("Configuración de Base de Datos", size=24, weight="bold"),
                ft.Divider(height=20),
                ft.TextField(label="Host", hint_text="Ingresa el host del servidor"),
                ft.TextField(label="Puerto", hint_text="Ingresa el puerto", keyboard_type=ft.KeyboardType.NUMBER),
                ft.TextField(label="Usuario", hint_text="Ingresa el usuario"),
                ft.TextField(label="Contraseña", hint_text="Ingresa la contraseña", password=True, can_reveal_password=True),
                ft.TextField(label="Base de Datos", hint_text="Nombre de la base de datos"),
                ft.Divider(height=20),
                ft.Row(
                    controls=[
                        ft.ElevatedButton("Guardar cambios", icon=ft.icons.SAVE, on_click=self._on_save),
                        ft.OutlinedButton("Probar conexión", icon=ft.icons.LINK, on_click=self._on_test_connection)
                    ],
                    alignment=ft.MainAxisAlignment.END
                ),
                ft.Divider(height=30),
                ft.Row(
                    controls=[
                        self.import_db_button,
                        self.export_db_button
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=20
                )
            ],
            spacing=16
        )

    def _setup_invoker(self):
        self.invoker = FileSaveInvoker(
            page=self.page,
            on_save=self._on_export_db,
            on_import=self._on_import_db,
            save_dialog_title="Guardar respaldo de base de datos",
            import_dialog_title="Importar base de datos desde archivo",
            allowed_extensions=["sql"],
            import_extensions=["sql"],
            file_name="respaldo_gestion_laboral.sql"
        )

        self.import_db_button = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Image(src="assets/buttons/import_database-button.png", width=24, height=24),
                    ft.Text("Importar Base de Datos")
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            on_click=self._mostrar_confirmacion_importar
        )

        self.export_db_button = self.invoker.get_save_button(
            text="Exportar Base de Datos",
            icon_path="assets/buttons/save-database-button.png"
        )

    def _mostrar_confirmacion_importar(self, e):
        print("🧪 _mostrar_confirmacion_importar fue llamado.")

        self.confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ Confirmación requerida"),
            content=ft.Text("Esta acción reemplazará toda la base de datos actual.\n¿Deseas continuar?"),
            actions=[
                ft.TextButton("Cancelar", on_click=self._cancelar_importacion),
                ft.TextButton("Sí, continuar", on_click=self._confirmar_importacion),
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        self.page.dialog = self.confirm_dialog
        self.confirm_dialog.open = True
        self.page.update()
        
    def _confirmar_importacion(self, e):
        print("🧪 Usuario confirmó importar.")
        self.confirm_dialog.open = False
        self.page.update()
        self.invoker.open_import()

    def _cancelar_importacion(self, e):
        print("🧪 Usuario canceló importación.")
        self.confirm_dialog.open = False
        self.page.update()



    def _on_import_db(self, path: str):
        try:
            success = self.db.importar_base_datos(path)
            if success:
                mostrar_mensaje(self.page, "✅ Importación exitosa", "La base de datos fue importada correctamente.")
            else:
                mostrar_mensaje(self.page, "⚠️ Error", "No se pudo importar la base de datos.")
        except Exception as e:
            mostrar_mensaje(self.page, "❌ Error crítico", f"Ocurrió un error:\n{e}")

    def _on_export_db(self, path: str):
        try:
            success = self.db.exportar_base_datos(path)
            if success:
                mostrar_mensaje(self.page, "✅ Exportación completa", "La base de datos fue exportada exitosamente.")
            else:
                mostrar_mensaje(self.page, "⚠️ Error", "No se pudo exportar la base de datos.")
        except Exception as e:
            mostrar_mensaje(self.page, "❌ Error al exportar", f"Ocurrió un error:\n{e}")

    def _on_save(self, e):
        print("🧪 Guardar cambios en configuración de base de datos")

    def _on_test_connection(self, e):
        print("🧪 Probar conexión a la base de datos")
