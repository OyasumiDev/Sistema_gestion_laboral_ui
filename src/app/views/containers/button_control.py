# app/views/containers/button_control.py

import flet as ft
from app.core.app_state import AppState

class ButtonControl(ft.GestureDetector):
    def __init__(
        self,
        icon_src: str,
        label: str,
        route: str,
        expandido: bool,
        fg: str,
        icon_bg: str | None = None,    # <— nuevo parámetro
    ):
        self.route = route

        # Contenedor del icono, bgcolor acepta None (transparente)
        icon = ft.Container(
            bgcolor=icon_bg,
            padding=6,
            border_radius=6,
            content=ft.Image(src=icon_src, width=24, height=24)
        )

        texto = ft.Text(label, visible=expandido, size=12, color=fg)

        # Row con icono y texto (o solo icono si expandido=False)
        fila = ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[icon, texto]
        )

        # Llamada a super(); GestureDetector admite on_tap
        super().__init__(content=fila, on_tap=self._on_tap)

    def _on_tap(self, e):
        # Navegación usando la misma página de AppState
        page = AppState().page
        page.go(self.route)
