# app/views/containers/database_settings_area.py

import flet as ft

class DatabaseSettingsArea(ft.Container):
    def __init__(self):
        super().__init__(
            expand=True,
            padding=20,
            content=ft.Column(
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
                    )
                ],
                spacing=16
            )
        )

    def _on_save(self, e):
        # Aquí irá la lógica para guardar la configuración
        print("Guardar cambios en configuración de base de datos")

    def _on_test_connection(self, e):
        # Aquí irá la lógica para probar la conexión a la base de datos
        print("Probar conexión a la base de datos")


# app/views/database_settings_view.py

import flet as ft
from app.views.containers.database_settings_area import DatabaseSettingsArea
from app.views.containers.navbar_container import NavBarContainer

class DatabaseSettingsView(ft.View):
    def __init__(self):
        super().__init__(route="/settings/db")
        self.navbar = NavBarContainer(is_root=True, modo_settings=True)
        self.database_area = DatabaseSettingsArea()

        self.controls = [
            ft.Row(
                controls=[
                    self.navbar,
                    self.database_area
                ],
                expand=True
            )
        ]

    def update_content(self, section: str):
        self.navbar._build()
        # En este caso siempre mostramos el área de base de datos.
