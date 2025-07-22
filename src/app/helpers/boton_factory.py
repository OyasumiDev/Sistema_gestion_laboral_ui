import flet as ft
from typing import Callable


class BotonFactory:
    def __init__(self):
        pass

    def crear_boton_accion(self, icon_name: str, tooltip: str, color: str, on_click: Callable) -> ft.IconButton:
        return ft.IconButton(
            icon=icon_name,
            icon_size=20,
            icon_color=color,
            tooltip=tooltip,
            on_click=on_click
        )

    def crear_boton_editar(self, on_click: Callable) -> ft.IconButton:
        return self.crear_boton_accion(ft.icons.EDIT, "Editar registro", ft.colors.BLUE_600, on_click)

    def crear_boton_eliminar(self, on_click: Callable) -> ft.IconButton:
        return self.crear_boton_accion(ft.icons.DELETE_OUTLINE, "Eliminar registro", ft.colors.RED_600, on_click)

    def crear_boton_guardar(self, on_click: Callable) -> ft.IconButton:
        return self.crear_boton_accion(ft.icons.SAVE, "Guardar cambios", ft.colors.GREEN_600, on_click)

    def crear_boton_cancelar(self, on_click: Callable) -> ft.IconButton:
        return self.crear_boton_accion(ft.icons.CANCEL, "Cancelar acción", ft.colors.GREY_700, on_click)

    def crear_boton_agregar(self, on_click: Callable) -> ft.IconButton:
        return self.crear_boton_accion(ft.icons.ADD, "Agregar nuevo registro", ft.colors.PRIMARY, on_click)

    # ✅ Redefinido para que sea igual al usado en EmpleadosContainer
    def crear_boton_importar(self, on_click: Callable) -> ft.GestureDetector:
        return ft.GestureDetector(
            on_tap=lambda _: on_click(),
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row([
                    ft.Image(src="assets/buttons/import-button.png", width=20, height=20),
                    ft.Text("Importar", size=11, weight="bold")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=5)
            )
        )

    def crear_boton_exportar(self, on_click: Callable) -> ft.GestureDetector:
        return ft.GestureDetector(
            on_tap=lambda _: on_click(),
            content=ft.Container(
                padding=8,
                border_radius=12,
                bgcolor=ft.colors.SURFACE_VARIANT,
                content=ft.Row([
                    ft.Image(src="assets/buttons/export-button.png", width=20, height=20),
                    ft.Text("Exportar", size=11, weight="bold")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=5)
            )
        )


# Instancia única de la fábrica para helpers
_factory = BotonFactory()


def crear_boton_editar(on_click: Callable):
    return _factory.crear_boton_editar(on_click)


def crear_boton_eliminar(on_click: Callable):
    return _factory.crear_boton_eliminar(on_click)


def crear_boton_guardar(on_click: Callable):
    return _factory.crear_boton_guardar(on_click)


def crear_boton_cancelar(on_click: Callable):
    return _factory.crear_boton_cancelar(on_click)


def crear_boton_importar(on_click: Callable):
    return _factory.crear_boton_importar(on_click)


def crear_boton_exportar(on_click: Callable):
    return _factory.crear_boton_exportar(on_click)
