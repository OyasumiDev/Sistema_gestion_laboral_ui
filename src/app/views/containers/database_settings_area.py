import flet as ft
from app.core.app_state import AppState
from app.core.invokers.file_save_invoker import FileSaveInvoker
from app.core.interfaces.database_mysql import DatabaseMysql  # <- Importamos el manejador de base de datos

class DatabaseSettingsArea(ft.Container):
    def __init__(self):
        super().__init__(
            expand=True,
            padding=20
        )

        self.page = AppState().page  # Página actual
        self.db = DatabaseMysql()    # Instancia de conexión a la BD
        self._setup_invoker()

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
                self.import_db_button  # Botón de importar base de datos
            ],
            spacing=16
        )

    def _setup_invoker(self):
        """Configura el manejador de importar archivos."""
        self.invoker = FileSaveInvoker(
            page=self.page,
            on_save=self._dummy_save,
            on_import=self._on_import_db,
            save_dialog_title="Guardar archivo",
            import_dialog_title="Importar Base de Datos",
            allowed_extensions=["txt", "csv"],   # extensiones permitidas para guardar (por si después quieres)
            import_extensions=["sql"]            # extensiones permitidas para importar
        )
        self.import_db_button = self.invoker.get_import_button(
            text="Importar Base de Datos",
            icon_path="assets/buttons/import_database-button.png"
        )

    def _dummy_save(self, path: str):
        """Placeholder para guardar archivos."""
        print(f"Guardar en: {path}")

    def _on_import_db(self, path: str):
        """Importa una base de datos desde un archivo seleccionado."""
        print(f"Importando base de datos desde: {path}")
        try:
            self.db.import_db(path)
            self.page.snack_bar = ft.SnackBar(
                ft.Text("✅ Base de datos importada exitosamente."),
                bgcolor=ft.colors.GREEN
            )
        except Exception as e:
            self.page.snack_bar = ft.SnackBar(
                ft.Text(f"❌ Error al importar base de datos: {e}"),
                bgcolor=ft.colors.RED
            )
        self.page.snack_bar.open = True
        self.page.update()

    def _on_save(self, e):
        """Guardar cambios en la configuración de la base de datos."""
        print("Guardar cambios en configuración de base de datos")

    def _on_test_connection(self, e):
        """Probar la conexión a la base de datos."""
        print("Probar conexión a la base de datos")
