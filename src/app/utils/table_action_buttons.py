import flet as ft
from typing import Callable

def crear_boton_accion(icon_name: str, tooltip: str, color: str, on_click: Callable) -> ft.IconButton:
    return ft.IconButton(
        icon=icon_name,
        icon_size=20,
        icon_color=color,
        tooltip=tooltip,
        on_click=on_click
    )

def crear_boton_editar(on_click: Callable) -> ft.IconButton:
    return crear_boton_accion(
        icon_name=ft.icons.EDIT,
        tooltip="Editar registro",
        color=ft.colors.BLUE_600,
        on_click=on_click
    )

def crear_boton_eliminar(on_click: Callable) -> ft.IconButton:
    return crear_boton_accion(
        icon_name=ft.icons.DELETE_OUTLINE,
        tooltip="Eliminar registro",
        color=ft.colors.RED_600,
        on_click=on_click
    )
