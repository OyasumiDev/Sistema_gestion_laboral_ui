# app/views/containers/menu_buttons_area.py
import flet as ft
from app.views.containers.button_control import ButtonControl

class MenuButtonsArea(ft.Column):
    def __init__(
        self,
        is_root: bool,
        expanded: bool,
        fg: str,
        btn_bg: str            # <— nuevo parámetro: fondo de cada botón
    ):
        # Definición de ítems de menú
        menu_items = [
            ("user-manager-area-button.png",    "Usuario",    "/home/usuario"),
            ("employees-button.png",            "Empleados",  "/home/empleados"),
            ("attendance-area-button.png",      "Asistencias","/home/asistencias"),
            ("payment-area-button.png",         "Pagos",      "/home/pagos"),
            ("nomina-area-button.png",          "Préstamos",  "/home/prestamos"),
            ("performance-area-button.png",     "Desempeño",  "/home/desempeno"),
            ("reports-area-button.png",         "Reportes",   "/home/reportes"),
        ]
        if is_root:
            menu_items.append((
                "user-manager-area-button.png",
                "Gestión de Usuarios",
                "/home/usuarios"
            ))

        # Crear cada botón pasando btn_bg a icon_bg
        menu_btns = [
            ButtonControl(
                icon_src = f"assets/buttons/{icon}",
                label    = label,
                route    = route,
                expandido= expanded,
                fg        = fg,
                icon_bg   = btn_bg    # aquí
            )
            for icon, label, route in menu_items
        ]

        super().__init__(
            spacing = 16,
            controls= menu_btns
        )
