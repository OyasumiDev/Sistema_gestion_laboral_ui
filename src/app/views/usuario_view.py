import flet as ft
from app.views.containers.usuarios_container import UsuariosContainer

class UsuarioView(ft.View):
    """Vista de Usuario"""
    def __init__(self):
        super().__init__(
            route="/home/usuario",
            controls=[
                ft.Column(
                    expand=True,
                    controls=[
                        ft.Text("Área actual: Usuarios", size=20, weight="bold"),
                        UsuariosContainer()  # Aquí sí va el contenedor entero
                    ]
                )
            ]
        )
