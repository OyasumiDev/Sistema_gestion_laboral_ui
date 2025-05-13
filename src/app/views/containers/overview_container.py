import flet as ft
from app.core.app_state import AppState


class OverviewContainer(ft.Container):
    def __init__(self):
        super().__init__(expand=True, padding=20)
        self.page = AppState().page
        self.content = self._build_layout()

    def _build_layout(self):
        return ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(
                    "BIENVENIDO AL SISTEMA DE GESTION DE LA EMPRESA",
                    size=28,
                    weight="bold",
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Divider(thickness=2, height=30),
                ft.Image(
                    src="assets/logos/logo_empresa.jpg",
                    width=1800,
                    height=700,
                    fit=ft.ImageFit.CONTAIN
                )
            ]
        )