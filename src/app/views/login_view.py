import flet as ft
from app.views.containers.login_container import LoginContainer

class LoginView(ft.View):
    def __init__(self):
        super().__init__(
            route='/login',
            controls=[LoginContainer()],
            appbar=ft.AppBar(
                title=ft.Text("Inicio de sesión"),
                bgcolor=ft.Colors.ON_SURFACE_VARIANT
            ),
            vertical_alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
