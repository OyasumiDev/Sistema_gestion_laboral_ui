import flet as ft

class UsuarioView(ft.View):
    """Vista de Usuario"""
    def __init__(self):
        super().__init__(
            route="/home/usuario",
            controls=[
                ft.Text("Vista de Usuario", size=20)
            ]
        )
