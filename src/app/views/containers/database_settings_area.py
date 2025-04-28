# app/views/containers/database_settings_area.py

import flet as ft
from app.core.app_state import AppState
from app.core.invokers.file_save_invoker import FileSaveInvoker  # <--- asegúrate de importar tu invoker correctamente

class DatabaseSettingsArea(ft.Container):
    def __init__(self):
        super().__init__(
            expand=True,
            padding=20
        )

        self.page = AppState().page  # Obtener la página actual de la app
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
                ft.Divider(height=30),  # separación extra
                self.import_db_button   # <-- Aquí metemos el nuevo botón de importar
            ],
            spacing=16
        )

    def _setup_invoker(self):
        """Configura el manejador de guardar/importar archivos."""
        self.invoker = FileSaveInvoker(
            page=self.page,
            on_save=self._dummy_save,   # este lo puedes usar o ignorar
            on_import=self._on_import_db  # Aquí manejamos la importación real
        )
        self.import_db_button = self.invoker.get_import_button()

    def _dummy_save(self, path: str):
        # Este método está de placeholder si quieres usar guardar en algún momento
        print(f"Guardar en: {path}")

    def _on_import_db(self, path: str):
        # Aquí manejas la lógica real de importar la base de datos
        print(f"Importar base de datos desde: {path}")
        # Aquí pondrías tu lógica de cargar el archivo a MySQL o lo que necesites

    def _on_save(self, e):
        # Lógica para guardar configuración
        print("Guardar cambios en configuración de base de datos")

    def _on_test_connection(self, e):
        # Lógica para probar conexión
        print("Probar conexión a la base de datos")
